from ast import arg
import multiprocessing
import argparse
import pathlib
from typing import *
import json
import sys
import asyncio
from datetime import datetime
from scipy.optimize import differential_evolution
import os

import jpype
import jpype.imports
from jpype.types import *

class SimulationError(Exception):
    pass

class ParameterDefinitions:
    fixed = []
    variable = []
    def __init__(self, fixed: List[Tuple[str, float]], variable: List[Tuple[str, float]]):
        self.fixed = fixed
        self.variable = variable
        pass

    @staticmethod
    def from_file(path : pathlib.Path) -> 'ParameterDefinitions':
        try:
            with open(str(path), 'r') as f:
                parameters = json.load(f)
                fixed = [(k, v) for k, v in parameters['fixed'].items()]
                variable = [(k, v[0], v[1]) for k, v in parameters['variable'].items()]
                
                return ParameterDefinitions(fixed, variable)
        except Exception as e:
            print('Can\'t load parameters')
            print(e)
            exit(1)

    def get_variable_parameters_bounds(self):
        return list(map(lambda vp: (vp[1], vp[2]), self.variable))
    
    def __str__(self):
        ret = 'Fixed parameters:\n'
        for (k, v) in self.fixed:
            ret += f'\t{k} = {v}\n'
        
        ret += f'\nVariable parameters:\n'
        for (k, lb, ub) in self.variable:
            ret += f'\t{k} in [{lb} to {ub}]\n'
        ret += '\n\n'
        return ret

def print_pid(*args, **kwargs):
    pid = multiprocessing.current_process().name
    print(f'{pid}:', *args, **kwargs)
    sys.stdout.flush()


async def make_request(server_addr, server_port, setup_commands, go_command, end_report, stop_condition_report):
    req_obj = {
        'setupCommands': setup_commands,
        'goCommmand': go_command,
        'endReport': end_report,
        'stopConditionReport': stop_condition_report
    }

    print_pid('Connetting to the server...')
    reader, writer = await asyncio.open_connection(server_addr, server_port)

    print_pid('Sending request...')
    req_str = json.dumps(req_obj) + '\n'
    writer.write(req_str.encode())
    
    print_pid('Waiting for response...')
    resp_str = (await reader.readline()).decode()

    resp_obj = json.loads(resp_str)
    return resp_obj



def objective_function(variables : List[int], *args):
    (
        server_addr,
        server_port,
        scenario,
        parameter_definitions,
        num_samples
    ) = args

    # save current time
    start_time = datetime.now()

    # create setup commands list
    print_pid('Generating setup commands...')
    setup_commads = [
        f'set selectScenario "{scenario}"',
        'load_scenario',
        'init-simulation'
    ]
    for (k, v) in parameter_definitions.fixed:
        setup_commads.append(f'set_parameter "{k}" {v}')    
    for i, (k, lb, ub) in enumerate(parameter_definitions.variable):
        v = variables[i]
        setup_commads.append(f'set_parameter "{k}" {v}')

    fitness_samples = []
    for i in range(num_samples):
        # make request
        resp_obj = asyncio.run(make_request(
            server_addr=server_addr,
            server_port=server_port,
            setup_commands=setup_commads,
            go_command='go-simulation',
            end_report='get-fitness',
            stop_condition_report='should-stop?'
        ))

        # check if server responded with an error
        if 'error' in resp_obj:
            err_msg = resp_obj['error']
            raise SimulationError(f'Server responded with an error: {err_msg}')

        # check if response is valid
        if 'simulationResult' not in resp_obj:
            raise RuntimeError('Server sent an invalid response')

        fitness = resp_obj['simulationResult']        
        fitness_samples.append(fitness)

    # calculate average fitness
    average_fitness = sum(fitness_samples) / len(fitness_samples)


    time_ellapsed = datetime.now() - start_time
    print_pid(f'Done in {time_ellapsed}. average: {average_fitness}; samples: {fitness_samples};')

    # return negative average fitness since differential_evolution tries to minimize
    return -average_fitness

def server_process(*args, **kwargs):
    (netlogo_home, wait_condition_server_not_started, wait_condition_evolution_not_ended) = args

    # get script folder path
    script_folder_path = pathlib.Path(str(os.path.realpath(__file__))).parent

    jpype.startJVM(
        classpath=[
            str(netlogo_home / 'app/*'),
            str(script_folder_path / 'SimulationServer.jar'),
            str(script_folder_path / 'lib/*')
        ]
    )

    from com.censacrof.dronesDifferentialEvolution import SimulationServer # type: ignore (suppress warning)

    print('Starting simulation server')
    simulation_server = SimulationServer(1234, '/home/francesco/git/drones-swarm/sciadro-3.1/SCD src.nlogo')
    simulation_server.start()

    # notify that the server has started
    with wait_condition_server_not_started:
        wait_condition_server_not_started.notify()
    
    # wait for the evolution to end
    with wait_condition_evolution_not_ended:
        wait_condition_evolution_not_ended.wait()
    
    # stop the server
    print('Stopping simulation server')
    simulation_server.stop()
    pass


if __name__ == '__main__':
    # shell argument parsing
    parser = argparse.ArgumentParser(
        description="Finds optimal parameters using the differential evolution algorithm",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('netlogo_home', type=pathlib.Path, help='Path of the top level directory of the Netlogo installation')
    parser.add_argument('model_path', type=pathlib.Path, help='Path of the model to optimize')
    parser.add_argument('scenario', type=str, help='Name of the scenario to simulate')
    parser.add_argument('parameters_path', type=pathlib.Path, help='Path of file containg the parameters\' bounds')
    parser.add_argument('-m','--max-iter', type=int, default=1, help='Maximum number of iterations of the differential evolution algorithm')
    parser.add_argument('-s','--samples', type=int, default=1, help='Number of samples for each individual')
    args = parser.parse_args()


    # create a simulation server process
    manager = multiprocessing.Manager()
    wait_condition_server_not_started = manager.Condition()
    wait_condition_evolution_not_ended = manager.Condition()
    server_process = multiprocessing.Process(
        target=server_process,
        args=(
            args.netlogo_home,
            wait_condition_server_not_started,
            wait_condition_evolution_not_ended,
        )
    )
    server_process.start()

    # wait for the server to start
    with wait_condition_server_not_started:
        wait_condition_server_not_started.wait()

    print('Loading parameters...')
    parameter_definitions = ParameterDefinitions.from_file(args.parameters_path)
    print(parameter_definitions)
    
    workers = multiprocessing.cpu_count()
    popsize = max(1, workers // len(parameter_definitions.variable))
    max_func_evaluations = (args.max_iter + 1) * popsize * len(parameter_definitions.variable)

    try:
        res = differential_evolution(
            func=objective_function,
            bounds=parameter_definitions.get_variable_parameters_bounds(),
            args=(
                '127.0.0.1',                # server_addr
                1234,                       # server_port
                args.scenario,              # scenario
                parameter_definitions,      # parameter_definitions
                args.samples,               # num_samples
            ),
            workers=workers,
            updating='deferred',
            popsize=popsize,
            maxiter=args.max_iter,
            polish=False,
            tol=0.01,
            recombination=0.4,
            init='latinhypercube',
            disp=True
        )

        print(res)
        for i, (k, lb, ub) in enumerate(parameter_definitions.variable):
            v = res.x[i]
            print(f'\t{k}={v}')
    except SimulationError as e:
        print('An error has occured during a simulation.', e)

    # tell the server to stop
    with wait_condition_evolution_not_ended:
        wait_condition_evolution_not_ended.notify()

    # wait until the server stops
    server_process.join()

    pass