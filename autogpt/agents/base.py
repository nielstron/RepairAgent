from __future__ import annotations

import re
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, Optional
import json

if TYPE_CHECKING:
    from autogpt.config import AIConfig, Config

    from autogpt.models.command_registry import CommandRegistry

from autogpt.llm.base import ChatModelResponse, ChatSequence, Message
from autogpt.llm.providers.openai import OPEN_AI_CHAT_MODELS, get_openai_command_specs
from autogpt.llm.utils import count_message_tokens, create_chat_completion
from autogpt.logs import logger
from autogpt.memory.message_history import MessageHistory
from autogpt.prompts.prompt import DEFAULT_TRIGGERING_PROMPT

CommandName = str
CommandArgs = dict[str, str]
AgentThoughts = dict[str, Any]

class BaseAgent(metaclass=ABCMeta):
    """Base class for all Auto-GPT agents."""

    ThoughtProcessID = Literal["one-shot"]

    def __init__(
        self,
        ai_config: AIConfig,
        command_registry: CommandRegistry,
        config: Config,
        big_brain: bool = True,
        default_cycle_instruction: str = DEFAULT_TRIGGERING_PROMPT,
        cycle_budget: Optional[int] = 1,
        send_token_limit: Optional[int] = None,
        summary_max_tlength: Optional[int] = None,
    ):
        self.ai_config = ai_config
        """The AIConfig or "personality" object associated with this agent."""

        self.command_registry = command_registry
        """The registry containing all commands available to the agent."""

        self.config = config
        """The applicable application configuration."""

        self.big_brain = big_brain
        """
        Whether this agent uses the configured smart LLM (default) to think,
        as opposed to the configured fast LLM.
        """

        self.default_cycle_instruction = default_cycle_instruction
        """The default instruction passed to the AI for a thinking cycle."""

        self.cycle_budget = cycle_budget
        """
        The number of cycles that the agent is allowed to run unsupervised.

        `None` for unlimited continuous execution,
        `1` to require user approval for every step,
        `0` to stop the agent.
        """

        self.cycles_remaining = cycle_budget
        """The number of cycles remaining within the `cycle_budget`."""

        self.cycle_count = 0
        """The number of cycles that the agent has run since its initialization."""

        self.system_prompt = ai_config.construct_full_prompt(config)
        """
        The system prompt sets up the AI's personality and explains its goals,
        available resources, and restrictions.
        """

        llm_name = self.config.smart_llm if self.big_brain else self.config.fast_llm
        self.llm = OPEN_AI_CHAT_MODELS[llm_name]
        """The LLM that the agent uses to think."""

        self.send_token_limit = send_token_limit or self.llm.max_tokens * 3 // 4
        """
        The token limit for prompt construction. Should leave room for the completion;
        defaults to 75% of `llm.max_tokens`.
        """

        self.history = MessageHistory(
            self.llm,
            max_summary_tlength=summary_max_tlength or self.send_token_limit // 6,
        )

        # These are new attributes used to construct the prompt
        """
        {
            "file_path":
                    {
                        (XX, YY): [...]
                    }
                
        }
        """
        self.read_files = {}

        """
        {
            "file_path": [
                {
                    "lines_range": (XX, YY),
                    "lines_list": [...]
                }
            ]
        }
        """
        self.suggested_fixes = {}

        """
        [
            {
                "query": [... list of search keywords],
                "result": dictionary of search result
            }
        ]
        """
        self.search_queries = []


        """
        {
            "get_info": "...",
            "run_tests":
        }
        """
        self.bug_report = {}
        self.commands_history = []
        self.human_feedback = []
        self.ask_chatgpt = None
        self.current_state = ""

    def construct_read_files(self, command_name = "read_range"):
        skip_next = False
        read_files = {}
        messages_history = [msg for _, msg in enumerate(self.history)]
        for i in range(len(messages_history)):
            if skip_next:
                continue
            skip_next = False
            msg = messages_history[i]
            if msg.role == "assistant":
                command_dict = json.loads(msg.content)
                if command_dict["command"]["name"] == command_name:
                    lines_range=(
                        command_dict["command"]["args"]["startline"],
                        command_dict["command"]["args"]["endline"])
                    file_path = command_dict["command"]["args"]["filepath"]
                    if i < len(messages_history) - 1:
                        j = i + 1
                        next_msg = messages_history[j]
                        if next_msg.role == "system":
                            if "Command {} returned:".format(command_name) in next_msg.content:
                                read_result = next_msg.content
                                skip_next= True
                            else:
                                read_result = None
                                skip_next = False
                    if read_result:
                        if file_path in read_files:
                            read_files[file_path][lines_range] = read_result
                        else:
                            read_files[file_path] = {
                                lines_range: read_result
                            }
                    else:
                        skip_next = False
                else:
                    skip_next = False
        self.read_files = read_files

    def construct_commands_history(self):
        messages_history = [msg for _, msg in enumerate(self.history)]
        commands_history = []
        for i in range(len(messages_history)):
            msg = messages_history[i]
            if msg.role == "assistant":
                command_dict = json.loads(msg.content)
                commands_history.append(command_dict["command"]["name"] + " , your reason for executing this command was: '{}'".format(
                            command_dict["thoughts"]["text"]
                        )
                    )

        self.commands_history = commands_history

    def construct_suggested_fixes(self, command_name = "write_range"):
        skip_next = False
        suggested_fixes = {}
        messages_history = [msg for _, msg in enumerate(self.history)]
        for i in range(len(messages_history)):
            if skip_next:
                continue
            skip_next = False
            msg = messages_history[i]
            if msg.role == "assistant":
                command_dict = json.loads(msg.content)
                if command_dict["command"]["name"] == command_name:
                    lines_range=(
                        command_dict["command"]["args"]["startline"],
                        command_dict["command"]["args"]["endline"])
                    file_path = command_dict["command"]["args"]["filepath"]
                    lines_list = command_dict["command"]["args"]["lines_list"]
                    
                    if file_path in suggested_fixes:
                        suggested_fixes[file_path].append({
                            "lines_range": lines_range,
                            "lines_list": lines_list
                        })
                    else:
                        suggested_fixes[file_path] = [{
                            "lines_range": lines_range,
                            "lines_list": lines_list
                        }]
        self.suggested_fixes = suggested_fixes
 
    def construct_human_feedback(self):
        human_feedback = []
        messages_history = [msg for _, msg in enumerate(self.history)]
        for i in range(len(messages_history)):
            msg = messages_history[i]
            if msg.role == "system":
                if msg.content.startswith("Human feedback"):
                    human_feedback.append(msg.content)
        self.human_feedback = human_feedback

        
    def construct_search_queries(self, command_name="search_code_base"):
        skip_next = False
        search_queries = []
        search_result = None
        messages_history = [msg for _, msg in enumerate(self.history)]
        for i in range(len(messages_history)):
            if skip_next:
                continue
            skip_next = False
            msg = messages_history[i]
            if msg.role == "assistant":
                command_dict = json.loads(msg.content)
                if command_dict["command"]["name"] == command_name:
                    key_words = command_dict["command"]["args"]["key_words"]
                    if i < len(messages_history) - 1:
                        j = i + 1
                        next_msg = messages_history[j]
                        if next_msg.role == "system":
                            if "Command {} returned:".format(command_name) in next_msg.content:
                                search_result = next_msg.content
                                skip_next= True
                            else:
                                search_result = None
                    if search_result:
                        search_queries.append({
                            "query": key_words,
                            "result": search_result
                        })
        self.search_queries = search_queries

    def construct_bug_report(self):
        get_info = ""
        run_tests = ""
        failing_test_code = ""
        messages_history = [msg for _, msg in enumerate(self.history)]
        for i in range(len(messages_history)):
            msg = messages_history[i]
            if msg.role == "assistant":
                command_dict = json.loads(msg.content)
                if command_dict["command"]["name"] == "get_info":
                    if i < len(messages_history) - 1:
                        j = i + 1
                        next_msg = messages_history[j]
                        get_info = next_msg.content
                        break

        for i in range(len(messages_history)):
            msg = messages_history[i]
            if msg.role == "assistant":
                command_dict = json.loads(msg.content)
                if command_dict["command"]["name"] == "run_tests":
                    if i < len(messages_history) - 1:
                        j = i + 1
                        next_msg = messages_history[j]
                        run_tests = next_msg.content
                        break

        failing_test_code = ""
        for i in range(len(messages_history)):
            msg = messages_history[i]    
            if msg.role == "assistant":
                command_dict = json.loads(msg.content)
                if command_dict["command"]["name"] == "extract_test_code":
                    if i < len(messages_history) - 1:
                        j = i + 1
                        next_msg = messages_history[j]
                        failing_test_code += "Extracting test code from file {} returned: ".format(command_dict["command"]["args"]["test_file_path"]) + next_msg.content + "\n"

        if get_info or run_tests or failing_test_code:
            self.bug_report = {"get_info": get_info, "run_tests": run_tests, "failing_test_code": failing_test_code}


    def construct_state(self):
        pass
    def think(
        self,
        instruction: Optional[str] = None,
        thought_process_id: ThoughtProcessID = "one-shot",
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Runs the agent for one cycle.

        Params:
            instruction: The instruction to put at the end of the prompt.

        Returns:
            The command name and arguments, if any, and the agent's thoughts.
        """

        instruction = instruction or self.default_cycle_instruction

        prompt: ChatSequence = self.construct_prompt(instruction, thought_process_id)
        prompt = self.on_before_think(prompt, thought_process_id, instruction)
        ## This is a line added by me to save prompts at each step
        prompt_text = prompt.dump()
        start_i = prompt_text.find("Locate the bug within the project")
        end_i = prompt_text.find("),running test cases will help you to achieve this first goal")
        in_between = prompt_text[start_i:end_i]
        project_name, bug_index= in_between.replace("Locate the bug within the project \"", "").replace('" (index of bug = ', " ").replace(")", "").split(" ")[:2]

        with open("prompt_history_{}_{}".format(project_name, bug_index), "a+") as patf:
            patf.write(prompt.dump())
        raw_response = create_chat_completion(
            prompt,
            self.config,
            functions=get_openai_command_specs(self.command_registry)
            if self.config.openai_functions
            else None,
        )
        self.cycle_count += 1

        return self.on_response(raw_response, thought_process_id, prompt, instruction)

    @abstractmethod
    def execute(
        self,
        command_name: str | None,
        command_args: dict[str, str] | None,
        user_input: str | None,
    ) -> str:
        """Executes the given command, if any, and returns the agent's response.

        Params:
            command_name: The name of the command to execute, if any.
            command_args: The arguments to pass to the command, if any.
            user_input: The user's input, if any.

        Returns:
            The results of the command.
        """
        ...

    def construct_base_prompt(
        self,
        thought_process_id: ThoughtProcessID,
        prepend_messages: list[Message] = [],
        append_messages: list[Message] = [],
        reserve_tokens: int = 0,
    ) -> ChatSequence:
        """Constructs and returns a prompt with the following structure:
        1. System prompt
        2. `prepend_messages`
        3. Message history of the agent, truncated & prepended with running summary as needed
        4. `append_messages`

        Params:
            prepend_messages: Messages to insert between the system prompt and message history
            append_messages: Messages to insert after the message history
            reserve_tokens: Number of tokens to reserve for content that is added later
        """

        prompt = ChatSequence.for_model(
            self.llm.name,
            [Message("system", self.system_prompt)] + prepend_messages,
        )

        ## added this part to change the prompt structure
        self.construct_read_files()
        self.construct_suggested_fixes()
        self.construct_search_queries()
        self.construct_bug_report()
        self.construct_commands_history()
        self.construct_human_feedback()

        context_prompt = "What follows are sections of the most important information you gathered so far about the current bug.\
        Use the following info to suggest a fix for the buggy code:\n"
        read_files_section = "## Read lines:\n"
        if self.read_files:
            for f in self.read_files:
                for r in self.read_files[f]:
                    read_files_section += "Lines {} to {} from file: {}\n{}\n\n".format(r[0], r[1], f, self.read_files[f][r])
        else:
            read_files_section+="No files have been read so far.\n"

        suggested_fixes_section = "## Suggested fixes:\n"+"This is the list of suggested fixes so far but none of them worked:\n"
        if self.suggested_fixes:
            for f in self.suggested_fixes:
                for fx in self.suggested_fixes[f]:
                    suggested_fixes_section += "###Fix:\nLines {} to {} from file {} were replaced with the following:\n{}\n\n".format(
                        fx["lines_range"][0],
                        fx["lines_range"][1],
                        f,
                        fx["lines_list"])
        else:
            suggested_fixes_section += "No fixes were suggested yet.\n"


        search_queries = "## Executed search queries within the code base:\n"
        if self.search_queries:
            for s in self.search_queries:
                search_queries += "Searching keywords: {}, returned the following results:\n{}\n\n".format(s["query"], s["result"])
        else:
            search_queries += "No search queries executed so far.\n"

        bug_report = "## Info about the bug (bug report summary):\n"

        if self.bug_report:
            bug_report += ("### Bug info:\n" if self.bug_report["get_info"] else "") + self.bug_report["get_info"] + "\n" +\
            ("### Test cases results:\n" if self.bug_report["run_tests"] else "") + self.bug_report["run_tests"] +"\n" +\
            ("### The code of the failing test cases:\n" if self.bug_report["failing_test_code"] else "")+ self.bug_report["failing_test_code"]+"\n"
        else:
            bug_report += "No info was collected about the bug so far. You can get more info about the bug by running the commands: get_info and run_tests.\n"
        
        commands_history = "## The list of commands you have executed so far:\n"
        if self.commands_history:
            commands_history += "\n".join(self.commands_history)

        human_feedback = "## The list of human feedbacks:\n"
        if self.human_feedback:
            human_feedback += "\n".join(self.human_feedback)
        context_prompt += read_files_section + "\n" + suggested_fixes_section + "\n" + search_queries + "\n" +\
            bug_report + "\n" + commands_history + "\n" + human_feedback +\
            "\n" + "## THE END OF ALL COLLECTED INFO SECTIONS, AFTER THIS YOU WILL SEE THE LAST EXECUTED COMMAND AND ITS RESULT, CONTINUE YOUR REASONING FROM THERE ##"
        prompt.append(Message("system", context_prompt))
        
        ## The following is the original code, uncomment when needed to roll back
        """
       # Reserve tokens for messages to be appended later, if any
        reserve_tokens += self.history.max_summary_tlength
        if append_messages:
            reserve_tokens += count_message_tokens(append_messages, self.llm.name)

        # Fill message history, up to a margin of reserved_tokens.
        # Trim remaining historical messages and add them to the running summary.
        history_start_index = len(prompt)
        trimmed_history = add_history_upto_token_limit(
            prompt, self.history, self.send_token_limit - reserve_tokens
        )
        
        if trimmed_history:
            new_summary_msg, _ = self.history.trim_messages(list(prompt), self.config)
            prompt.insert(history_start_index, new_summary_msg)

        """
        if len(self.history) > 2:
            last_command = self.history[-2]
            command_result = self.history[-1]
            last_command_section = "## The last command you executed was:\n {}\n## The result of executing the last command is:\n {}".format(last_command.content, command_result.content)
            append_messages.append(Message("system", last_command_section))
        if append_messages:
            prompt.extend(append_messages)

        return prompt

    def construct_prompt(
        self,
        cycle_instruction: str,
        thought_process_id: ThoughtProcessID,
    ) -> ChatSequence:
        """Constructs and returns a prompt with the following structure:
        1. System prompt
        2. Message history of the agent, truncated & prepended with running summary as needed
        3. `cycle_instruction`

        Params:
            cycle_instruction: The final instruction for a thinking cycle
        """

        if not cycle_instruction:
            raise ValueError("No instruction given")

        cycle_instruction_msg = Message("user", cycle_instruction)
        cycle_instruction_tlength = count_message_tokens(
            cycle_instruction_msg, self.llm.name
        )

        append_messages: list[Message] = []

        response_format_instr = self.response_format_instruction(thought_process_id)
        if response_format_instr:
            append_messages.append(Message("system", response_format_instr))

        prompt = self.construct_base_prompt(
            thought_process_id,
            append_messages=append_messages,
            reserve_tokens=cycle_instruction_tlength,
        )

        # ADD user input message ("triggering prompt")
        prompt.append(cycle_instruction_msg)

        return prompt

    # This can be expanded to support multiple types of (inter)actions within an agent
    def response_format_instruction(self, thought_process_id: ThoughtProcessID) -> str:
        if thought_process_id != "one-shot":
            raise NotImplementedError(f"Unknown thought process '{thought_process_id}'")

        RESPONSE_FORMAT_WITH_COMMAND = """```ts
        interface Response {
            thoughts: {
                // Thoughts
                text: string;
                reasoning: string;
                // Short markdown-style bullet list that conveys the long-term plan
                plan: string;
                // Constructive self-criticism
                criticism: string;
                // Summary of thoughts to say to the user
                speak: string;
            };
            command: {
                name: string;
                args: Record<string, any>;
            };
        }
        ```"""

        RESPONSE_FORMAT_WITHOUT_COMMAND = """```ts
        interface Response {
            thoughts: {
                // Thoughts
                text: string;
                reasoning: string;
                // Short markdown-style bullet list that conveys the long-term plan
                plan: string;
                // Constructive self-criticism
                criticism: string;
                // Summary of thoughts to say to the user
                speak: string;
            };
        }
        ```"""

        response_format = re.sub(
            r"\n\s+",
            "\n",
            RESPONSE_FORMAT_WITHOUT_COMMAND
            if self.config.openai_functions
            else RESPONSE_FORMAT_WITH_COMMAND,
        )

        use_functions = self.config.openai_functions and self.command_registry.commands
        return (
            f"Respond strictly with JSON{', and also specify a command to use through a function_call' if use_functions else ''}. "
            "The JSON should be compatible with the TypeScript type `Response` from the following:\n"
            f"{response_format}\n"
        )

    def on_before_think(
        self,
        prompt: ChatSequence,
        thought_process_id: ThoughtProcessID,
        instruction: str,
    ) -> ChatSequence:
        """Called after constructing the prompt but before executing it.

        Calls the `on_planning` hook of any enabled and capable plugins, adding their
        output to the prompt.

        Params:
            instruction: The instruction for the current cycle, also used in constructing the prompt

        Returns:
            The prompt to execute
        """
        current_tokens_used = prompt.token_length
        plugin_count = len(self.config.plugins)
        for i, plugin in enumerate(self.config.plugins):
            if not plugin.can_handle_on_planning():
                continue
            plugin_response = plugin.on_planning(
                self.ai_config.prompt_generator, prompt.raw()
            )
            if not plugin_response or plugin_response == "":
                continue
            message_to_add = Message("system", plugin_response)
            tokens_to_add = count_message_tokens(message_to_add, self.llm.name)
            if current_tokens_used + tokens_to_add > self.send_token_limit:
                logger.debug(f"Plugin response too long, skipping: {plugin_response}")
                logger.debug(f"Plugins remaining at stop: {plugin_count - i}")
                break
            prompt.insert(
                -1, message_to_add
            )  # HACK: assumes cycle instruction to be at the end
            current_tokens_used += tokens_to_add
        return prompt

    def on_response(
        self,
        llm_response: ChatModelResponse,
        thought_process_id: ThoughtProcessID,
        prompt: ChatSequence,
        instruction: str,
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Called upon receiving a response from the chat model.

        Adds the last/newest message in the prompt and the response to `history`,
        and calls `self.parse_and_process_response()` to do the rest.

        Params:
            llm_response: The raw response from the chat model
            prompt: The prompt that was executed
            instruction: The instruction for the current cycle, also used in constructing the prompt

        Returns:
            The parsed command name and command args, if any, and the agent thoughts.
        """

        # Save assistant reply to message history
        self.history.append(prompt[-1])
        self.history.add(
            "assistant", llm_response.content, "ai_response"
        )  # FIXME: support function calls

        try:
            return self.parse_and_process_response(
                llm_response, thought_process_id, prompt, instruction
            )
        except SyntaxError as e:
            logger.error(f"Response could not be parsed: {e}")
            # TODO: tune this message
            self.history.add(
                "system",
                f"Your response could not be parsed: {e}"
                "\n\nRemember to only respond using the specified format above!",
            )
            return None, None, {}

        # TODO: update memory/context

    @abstractmethod
    def parse_and_process_response(
        self,
        llm_response: ChatModelResponse,
        thought_process_id: ThoughtProcessID,
        prompt: ChatSequence,
        instruction: str,
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Validate, parse & process the LLM's response.

        Must be implemented by derivative classes: no base implementation is provided,
        since the implementation depends on the role of the derivative Agent.

        Params:
            llm_response: The raw response from the chat model
            prompt: The prompt that was executed
            instruction: The instruction for the current cycle, also used in constructing the prompt

        Returns:
            The parsed command name and command args, if any, and the agent thoughts.
        """
        pass


def add_history_upto_token_limit(
    prompt: ChatSequence, history: MessageHistory, t_limit: int
) -> list[Message]:
    current_prompt_length = prompt.token_length
    insertion_index = len(prompt)
    limit_reached = False
    trimmed_messages: list[Message] = []
    for cycle in reversed(list(history.per_cycle())):
        messages_to_add = [msg for msg in cycle if msg is not None]
        tokens_to_add = count_message_tokens(messages_to_add, prompt.model.name)
        if current_prompt_length + tokens_to_add > t_limit:
            limit_reached = True

        if not limit_reached:
            # Add the most recent message to the start of the chain,
            #  after the system prompts.
            prompt.insert(insertion_index, *messages_to_add)
            current_prompt_length += tokens_to_add
        else:
            trimmed_messages = messages_to_add + trimmed_messages

    return trimmed_messages
