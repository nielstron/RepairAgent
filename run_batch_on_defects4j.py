import multiprocessing
import subprocess

def run_bash_script(param):
    try:
        subprocess.run(['bash', './run_on_defects4j.sh', *param], check=True)
        return multiprocessing.current_process().name
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")
        return None

if __name__ == '__main__':
    params_list = [("experimental_setups/batches/{}".format(i), "hyperparams.json") for i in range(36)]  # List of different parameter values
    finished_processes = []

    with multiprocessing.Pool() as pool:
        results = pool.map(run_bash_script, params_list)
        for result in results:
            if result:
                finished_processes.append(result)

    print("Finished processes:", finished_processes)