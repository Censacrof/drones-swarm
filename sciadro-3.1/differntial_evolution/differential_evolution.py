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
                fixed = []
                variable = []

                for line in f:
                    # matches fixed parameter: param = value
                    match = re.match(r'^\s*([A-z-_]+)\s*=\s*(\d+(?:\.\d+)?)\s*(?:#.*)?\s*$', line)
                    if match:
                        fixed.append((match.group(1), float(match.group(2))))
                        continue

                    # matches variable parameter: param = (lb, ub)
                    match = re.match(r'^\s*([A-z-_]+)\s*=\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)\s*(?:#.*)?\s*$', line)
                    if match:
                        variable.append((match.group(1) ,  float(match.group(2)), float(match.group(3))))
                        continue
                
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


   
def interpret_simulation(simulation_data):
    threshold = 1
    ticks_ellapsed_before_locate = []
    last_n_targets = 0
    time_slot_start = 0
    state = 'not_located'
    for tick, data in enumerate(simulation_data):
        n_targets, n_found = tuple(data)
        # print(tick, data, state)

        if n_targets != 0:
            if state == 'not_located':            
                percent = n_found / n_targets
                if percent >= threshold:
                    state = 'located'
                    ticks_ellapsed_before_locate.append(float(tick - time_slot_start))
            
                # else if time slot ended without locating
                elif last_n_targets != n_targets or tick == len(simulation_data) - 1:
                    if last_n_targets != 0:
                        estimate = 1000
                        if percent != 0:
                            estimate = threshold * float(tick - time_slot_start) / percent
                        ticks_ellapsed_before_locate.append(estimate)                    
                    time_slot_start = tick
            
            
            elif state == 'located':
                if last_n_targets != n_targets:
                    state = 'not_located'
                    time_slot_start = tick

        last_n_targets = n_targets
        pass

    return ticks_ellapsed_before_locate


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
        cmd = f'set {k} {v}'
        # print_pid('(fixed)', cmd)
        workspace.command(cmd)
    
    for i, (k, lb, ub) in enumerate(parameter_definitions.variable):
        v = variables[i]
        cmd = f'set {k} {v}'
        workspace.command(cmd)
        # print_pid('(variable)', cmd)

    print_pid('Simulating...')
    simulation_data = workspace.schedule_reporters(
        reporters=[
            'count patches with [ target = true ]',
            'count patches with [ target = true and status = "found" ]'
        ],
        start_at_tick=0,
        stop_at_tick=1500,
        go_command='go'
    )


    ticks_ellapsed_before_locate = interpret_simulation(simulation_data)
    avg = np.mean(ticks_ellapsed_before_locate)

    # print()    
    
    # ticks = 0
    # while ticks < 1500:
    #     workspace.command('go')
    #     n_targets = workspace.report('count patches with [ target = true ]')
    #     n_found = workspace.report('count patches with [ target = true and status = "found" ]')
    #     end_time_slot = workspace.report('endtimeSlot_float')
    #     print(f'target founds: {n_targets} / {n_found}; ets: {end_time_slot}')

    workspace.close_model()
    nl4py.delete_headless_workspace(workspace)

    time_ellapsed = (datetime.now() - start_time).seconds()
    print_pid(f'Done in {time_ellapsed} seconds! avg: {avg}')
    return avg


if __name__ == '__main__':
    # shell argument parsing
    parser = argparse.ArgumentParser(
        description="Finds optimal parameters using the differential evolution algorithm",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('netlogo_path', type=pathlib.Path, help='Path of the top level directory of the Netlogo installation')
    parser.add_argument('model_path', type=pathlib.Path, help='Path of the model to optimize')
    parser.add_argument('bounds_path', type=pathlib.Path, help='Path of file containg the parameters\' bounds')
    args = parser.parse_args()


    print('Initializing nl4py...')
    nl4py.initialize(args.netlogo_path)

    print('Loading parameters...')
    parameter_definitions = ParameterDefinitions.from_file(args.bounds_path)
    print(parameter_definitions)

    print('Executing differential evolution...')
    res = differential_evolution(
        func=objective_function,
        bounds=parameter_definitions.get_variable_parameters_bounds(),
        args=(args.model_path, parameter_definitions),
        workers=-1,
        updating='deferred'
    )

    print(res)