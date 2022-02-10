import multiprocessing
from scipy.optimize import differential_evolution

import jpype
import jpype.imports
from jpype.types import *


def server_process(*args, **kwargs):
    jpype.startJVM(
        classpath=[
            '/netlogo/app/netlogo-6.2.2.jar',
            'target/dronesDifferentialEvolution-1.0-SNAPSHOT.jar', 
            '/home/francesco/.m2/repository/com/google/code/gson/gson/2.8.9/gson-2.8.9.jar'
        ]
    )

    from com.censacrof.dronesDifferentialEvolution import SimulationServer


    print('Starting simulation server')
    simulation_server = SimulationServer(1234, '/home/francesco/git/drones-swarm/sciadro-3.1/SCD src.nlogo')
    simulation_server.runServer()
    pass


if __name__ == '__main__':

    # create a simulation server process
    server_process = multiprocessing.Process(
        target=server_process
    )
    server_process.start()

    server_process.join()

    pass