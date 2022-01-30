import nl4py
import argparse
import pathlib
import fire_model as fm
import os
import shutil
import sys
import re

if __name__ == '__main__':
    model_path = pathlib.Path(fm.__file__).parents[0] / 'fire.nlogo'

    # shell argument parsing
    parser = argparse.ArgumentParser(
        description="Generates a dynamic fire scenario",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('netlogo-home', type=pathlib.Path)
    parser.add_argument('-o', '--output', type=pathlib.Path, default=pathlib.Path('./fire_scenario'), help='Path of the generated scenario')
    parser.add_argument('-t', '--ticks', type=int, default=-1, help='Maximum number of ticks to simulate')
    parser.add_argument('-i', '--sample-interval', type=int, default=1, help='Ticks interval in between samples')
    parser.add_argument('-n', '--num-samples', type=int, default=-1, help='Maximum number of samples to take')
    parser.add_argument('-W', '--world-width', type=int, default=300, help='Width of the world in patches (min is 50)')
    parser.add_argument('-H', '--world-height', type=int, default=300, help='Width of the world in patches (min is 50)')
    parser.add_argument('-g', '--get-parameters', action='store_true', help='If set prints all parameters of the simulation to stdout')
    parser.add_argument('-e', '--execute', action='store_true', help='If set executes commands from stdin until EOF before setup')
    args = vars(parser.parse_args())

    # check value of parameters
    if args['ticks'] < -1:
        args['ticks'] = -1

    if args['sample_interval'] < 0:
        args['sample_interval'] = 0

    if args['num_samples'] < -1:
        args['num_samples'] = -1

    args['world_width'] = max(50, args['world_width'])
    args['world_height'] = max(50, args['world_height'])

    if not args['get_parameters']:
        print('Initializing nl4py...')
    nl4py.initialize(args['netlogo-home'])

    if not args['get_parameters']:
        print('Creating headless workspace...')
    workspace = nl4py.create_headless_workspace()

    if not args['get_parameters']:
        print('Opening fire model...')
    workspace.open_model(str(model_path))
    
    # if -g is set i print all the parameters of the model    
    if args['get_parameters']:
        params = workspace.get_param_names()
        ranges = workspace.get_param_ranges()
        for i in range(len(params)):
            print('; range {0}\nset {1} {2}\n'.format(
                ranges[i],
                params[i],
                '{0}{1}{0}'.format(
                    '"' if isinstance(ranges[0], str) else '',
                    ranges[0][0]
                )
            ))
        workspace.close_model()
        nl4py.delete_headless_workspace(workspace)
        exit(0)

    # setup output folders
    scenario_dir = (pathlib.Path('.') / args['output']).resolve()
    frames_dir = scenario_dir / 'frames'
    
    # if frame folder already exists i delete it and create it again
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir)

    # resizing the world accordingly
    cmd = 'resize-world -{0} {0} -{1} {1}'.format(
        args['world_width'] // 2,
        args['world_height'] // 2,
    )
    print(">", cmd)

    # if -e is set execute commands from stdin
    if args['execute']:
        print('Execute commands (send EOF to continue):')
        for line in sys.stdin:
            # if line is empty a comment ignore it
            if (re.match(r'(^\s*;.*|^\s*$)', line)):
                continue
            workspace.command(line)
            print(">", line)

    print('Running \'setup\' on the model...')
    workspace.command(cmd)
    workspace.command('setup')

    print('Simulating...')
    tick_count = 0
    sample_count = 0
    while (workspace.report('how-many-fires') > 0 and tick_count != args['ticks'] and sample_count != args['num_samples']):
        workspace.command('go')

        if tick_count % args['sample_interval'] == 0:
            frame_name = 'frame_{}'.format(sample_count)
            frame_path = frames_dir / frame_name
            print('(tick {})\tgenerating {}...'.format(
                tick_count,
                str(frame_name)
            ))
            workspace.command('save-fires "{}"'.format(
                str(frame_path)
            ))
            sample_count += 1
        tick_count += 1
    
    # export snapshot of the world in the final state
    print('Generating preview {}'.format(str(scenario_dir / 'snapshot.png')))
    workspace.command('export-view "{}"'.format(
        str(scenario_dir / 'snapshot.png')
    ))

    print('Closing fire model...')
    workspace.close_model()
    nl4py.delete_headless_workspace(workspace)
    pass