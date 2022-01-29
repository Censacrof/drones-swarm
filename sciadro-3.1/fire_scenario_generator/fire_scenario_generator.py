from importlib.resources import path
from threading import Thread
import nl4py
import argparse
import pathlib
import fire_model as fm
import os
import shutil

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generates a dynamic fire scenario")
    parser.add_argument('netlogo-home', type=pathlib.Path)
    parser.add_argument('-o', '--output', type=pathlib.Path, help='Name of the generated scenario')
    parser.add_argument('-t', '--ticks', type=int, help='Number of ticks to simulate')
    args = vars(parser.parse_args())
    model_path = pathlib.Path(fm.__file__).parents[0] / 'fire.nlogo'
    
    print(f'Initializing nl4py...')
    nl4py.initialize(args['netlogo-home'])

    print('Creating headless workspace...')
    workspace = nl4py.create_headless_workspace()

    print('Opening fire model...')
    workspace.open_model(str(model_path))

    ########    
    gen_scenario_name = args['output'] if args['output'] is not None else 'fireScenario'
    scenario_dir = pathlib.Path('.').resolve() / gen_scenario_name
    frames_dir = scenario_dir / 'frames'
    
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir)


    workspace.command('setup')
    count_max = args['ticks'] if args['ticks'] is not None else -1
    count = 0
    while (workspace.report('how-many-fires') > 0 and count != count_max):
        workspace.command('go')
        workspace.command('save-fires "{}"'.format(
            str(frames_dir / 'frame_{}'.format(count))
        ))

        count += 1

    print('Closing fire model...')
    workspace.close_model()
    nl4py.delete_headless_workspace(workspace)
    pass