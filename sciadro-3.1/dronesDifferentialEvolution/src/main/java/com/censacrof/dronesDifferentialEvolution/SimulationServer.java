package com.censacrof.dronesDifferentialEvolution;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.util.ArrayList;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import org.nlogo.headless.HeadlessWorkspace;

public class SimulationServer implements Runnable {
	public final int port;
	public final String modelPath;
	private ArrayList<HeadlessWorkspace> _workspaces;
	private Thread _listenerThread;
	private ServerSocket _serverSock;

	public SimulationServer(int port, String modelPath) {
		this.port = port;
		this.modelPath = modelPath;
		this._listenerThread = null;
	}

	public void start() throws InterruptedException {
		_workspaces = new ArrayList<>();
		_listenerThread = new Thread(this);
		_listenerThread.start();

		// wait untill _listenerThread is listening
		synchronized(this) {
			wait();
		}
	}

	public void stop() throws IOException {
		try {
			_serverSock.close();
			_listenerThread.interrupt();
			_listenerThread.join();
		} catch (InterruptedException ignore) { }
	}

	public void run() {
		try {
			_serverSock = new ServerSocket(
				this.port,
				100 // backlog
			);

			System.out.println("Listening on port " + this.port);

			// notify the the thread wating inside start()
			synchronized (this) {
				notify();
			}
			
			while (true) {
				Socket clientSock;
				try {
					clientSock = _serverSock.accept();
				} catch (SocketException e) {
					// the socket was closed => exit
					break;
				}

				System.out.println("Connection accepted");

				SimulationWorker simulationWorker = new SimulationWorker(clientSock, modelPath, _workspaces);
				Thread workerThread = new Thread(simulationWorker);
				workerThread.start();
			}
		} catch (IOException e) {
			System.out.println(e);
		}
	}
}


class SimulationWorker implements Runnable {
	private Socket _clientSock;
	public final String modelPath;
	private ArrayList<HeadlessWorkspace> _workspaces;

	public SimulationWorker(Socket clientSock, String modelPath, ArrayList<HeadlessWorkspace> workspaces) {
		this._clientSock = clientSock;
		this.modelPath = modelPath;
		this._workspaces = workspaces;
	}

	public void run() {
		System.out.println("Worker started");

		// read json from the socket
		try (
			BufferedReader bufferedReader = new BufferedReader(
				new InputStreamReader(_clientSock.getInputStream())
			)
		){
			String requestString = bufferedReader.readLine();

			if (requestString == null) {
				sendResponse(
					new SimulationRespose()
						.setError(true)
						.setResponseMessage("Empty request")
				);

				_clientSock.close();
				return;
			}
	
			// parse json
			System.out.println(requestString);
			SimulationRequest simulationRequest = new Gson().fromJson(requestString, SimulationRequest.class);

			if (simulationRequest == null) {
				sendResponse(
					new SimulationRespose()
						.setError(true)
						.setResponseMessage("Can't parse request")
				);

				_clientSock.close();
				return;
			}

			System.out.println(simulationRequest.getSetupCommands());

			// start simulation
			double simulationResult;
			try {
				simulationResult = simulate(simulationRequest);
			} catch (Exception e) {
				sendResponse(
					new SimulationRespose()
						.setError(true)
						.setResponseMessage(e.getMessage())
				);

				return;
			}
	
			try {	
				// respond
				SimulationRespose simulationRespose = new SimulationRespose()
					.setSimulationResult(simulationResult);
				sendResponse(simulationRespose);			
				
				// close connection
				_clientSock.close();
			} catch (IOException e) {
				System.out.println("Exception during response, " + e);
			}		

		} catch (IOException e) {
			System.out.println("Can't read from socket\n" + e);
			return;
		}
	}

	private double simulate(SimulationRequest simulationRequest) throws IOException {
		// check if all required fields inside simulationCommand are present
		if (
			simulationRequest.getSetupCommands() == null 
			|| simulationRequest.getGoCommmand() == null
			|| simulationRequest.getStopConditionReport() == null
			|| simulationRequest.getEndReport() == null
		) {
			throw new IllegalArgumentException("Invalid SimulationCommand, some of the required fields are missing");
		}

		// get a workspace if available
		HeadlessWorkspace workspace = null;
		synchronized(_workspaces) {
			if (_workspaces.size() > 0) {
				workspace = _workspaces.get(0);
				_workspaces.remove(0);
			}
		}

		// if there was no available workspace => create one
		if (workspace == null) {
			System.out.println("Creating workspace...");
			workspace = HeadlessWorkspace.newInstance();
			System.out.println("Opening model " + modelPath + " ...");
			workspace.open(modelPath);
			System.out.println("Done!");
		}

		// run all setup commands
		for (String cmd: simulationRequest.getSetupCommands()) {
			workspace.command(cmd);
		}

		// run the simulation
		while ((boolean) workspace.report(simulationRequest.getStopConditionReport())) {
			workspace.command(simulationRequest.getGoCommmand());
		}

		// save the workspace for future use
		synchronized (_workspaces) {
			_workspaces.add(workspace);
		}

		// return the value of the report
		return (double) workspace.report(simulationRequest.getEndReport());
	}

	private void sendResponse(SimulationRespose simulationRespose) throws IOException {
		// serialize simulationResponse
		Gson gson = new GsonBuilder().disableHtmlEscaping().create();
		String responseString = gson.toJson(simulationRespose);

		// send response through the socket
		try (
			PrintWriter printWriter = new PrintWriter(
				_clientSock.getOutputStream()
			)
		) {
			printWriter.println(responseString);
		}
	}

	private class SimulationRequest {
		private ArrayList<String> setupCommands;
		private String goCommmand;
		private String endReport;
		private String stopConditionReport;

		public ArrayList<String> getSetupCommands() {
			return setupCommands;
		}

		public String getGoCommmand() {
			return goCommmand;
		}

		public String getEndReport() {
			return endReport;
		}

		public String getStopConditionReport() {
			return stopConditionReport;
		}
	}

	@SuppressWarnings("unused")
	private class SimulationRespose {
		private String responseMessage;
		private Boolean error;
		private Double simulationResult;

		public SimulationRespose setSimulationResult(Double endReportValue) {
			this.simulationResult = endReportValue;
			return this;
		}

		public SimulationRespose setError(Boolean error) {
			this.error = error;
			return this;
		}

		public SimulationRespose setResponseMessage(String responseMessage) {
			this.responseMessage = responseMessage;
			return this;
		}
	}
}