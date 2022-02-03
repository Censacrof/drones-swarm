import argparse
import enum
from logging import exception
import pathlib
from pydoc import resolve
import nl4py
from typing import *
from numpy import mat, var
from scipy.optimize import differential_evolution
import re
import multiprocessing
import numpy as np
from datetime import date, datetime
import json
import sys

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


def objective_function(variables : List[int], *args):
    start_time = datetime.now()
    model_path, parameter_definitions, = args

    print_pid('Creating workspace...')
    workspace = nl4py.create_headless_workspace()

    print_pid('Opening model...')
    workspace.open_model(str(model_path))

    print_pid('Loading scenario...')
    workspace.command('set selectScenario "fire1"')
    workspace.command('load_scenario')

    print_pid('Setting parameters...')
    for (k, v) in parameter_definitions.fixed:
        cmd = f'set_parameter "{k}" {v}'
        # print_pid('(fixed)', cmd)
        workspace.command(cmd)
    
    for i, (k, lb, ub) in enumerate(parameter_definitions.variable):
        v = variables[i]
        cmd = f'set_parameter "{k}" {v}'
        workspace.command(cmd)
        # print_pid('(variable)', cmd)

    print_pid('Simulating...')
    workspace.command('run-simulation-with-moving-targets')
    fitness = workspace.report('fitness-moving-targets') # the lower the better

    workspace.close_model()
    nl4py.delete_headless_workspace(workspace)

    time_ellapsed = datetime.now() - start_time
    print_pid(f'Done in {time_ellapsed}! fitness value: {fitness}')
    return fitness


if __name__ == '__main__':
    multiprocessing.set_start_method('fork')

    # shell argument parsing
    parser = argparse.ArgumentParser(
        description="Finds optimal parameters using the differential evolution algorithm",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('netlogo_path', type=pathlib.Path, help='Path of the top level directory of the Netlogo installation')
    parser.add_argument('model_path', type=pathlib.Path, help='Path of the model to optimize')
    parser.add_argument('parameters_path', type=pathlib.Path, help='Path of file containg the parameters\' bounds')
    args = parser.parse_args()


    print('Initializing nl4py...')
    nl4py.initialize(args.netlogo_path)

    print('Loading parameters...')
    parameter_definitions = ParameterDefinitions.from_file(args.parameters_path)
    print(parameter_definitions)

    print('Executing differential evolution...')
    res = differential_evolution(
        func=objective_function,
        bounds=parameter_definitions.get_variable_parameters_bounds(),
        args=(args.model_path, parameter_definitions),
        workers=-1,
        updating='deferred',
        popsize=1,
        maxiter=5,
        polish=False,
        tol=0.01,
        disp=True
    )

    print(res)
    for i, (k, lb, ub) in enumerate(parameter_definitions.variable):
        v = res.x[i]
        print(f'\t{k}={v}')