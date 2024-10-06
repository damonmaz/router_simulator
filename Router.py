"""
Filename: Router.py
Author:   Damon Mazurek
"""

from socket import *
import threading
import time
import sys
import string
import pickle

# Const Global Variables
INFINITY = 999
NO_PARENT = -1
ALPHABET = list(string.ascii_uppercase)
SERVERNAME = "localhost"

router_labels = []

class Router:
    """
    A class to simulate a router in a network.

    This class implements the functionality of a router, including sending and receiving
    link state information, calculating shortest paths using Dijkstra's algorithm, and
    maintaining a forwarding table.
    """
    def __init__(self, router_id, router_port, config_file):
        """
        Initialize the Router object.

        Args:
            router_id (int): The ID of the router.
            router_port (int): The port number the router will use.
            config_file (str): The path to the configuration file.
        """
        # Sockets
        self.sender_socket = socket(AF_INET, SOCK_DGRAM) # Sender Socket for a router
        self.receiver_socket = socket(AF_INET, SOCK_DGRAM) # Reciever Socket for a router
        
        # Router info
        self.router_id = router_id
        self.router_port = router_port
        self.config_file = config_file
        
        # Neighbor router info
        self.neighbors_info = {}  # Store neighbor information {neighbor_id: (cost, neighbor_port)}
        self.neighbors_data = {}  # Store recieved neighbor data from receive_and_broadcast method
        self.neighbor_ports = []
        self.link_state = []  # Link state vector
        self.forwarding_table = {}  # Forwarding table {destination_id: next_hop_label}
        
        self.terminate_threads = False
        
        self.received_all = False
        self.shortest_distance = []
        self.prev_node = []
        self.path = []
        self.next_node = []

    def load_configuration(self):
        """
        Loads information about router from config file by reading the configuration 
        file and initializes the router's neighbors and link state information.
        """
        try:
            #Try to open config file. If it has stupid formatting where its last line is just a '\n' (LIKE config-A.txt), get rid of it
            with open(self.config_file, 'r') as file:
                lines = file.readlines()
                total_nodes = int(lines[0].strip())
                if lines[-1].strip() == '':
                    lines = lines[:-1]
            #Initialize self.neighbors and self.link_state
            # print(lines)
            for line in lines[1:]:
                parts = line.strip().split()
                # print(parts)
                neighbor_label, neighbor_id, cost, neighbor_port = parts
                neighbor_id, cost, neighbor_port = map(int, [neighbor_id, cost, neighbor_port])
                self.neighbors_info[neighbor_id] = [cost, neighbor_port] #Set value of self's neighbors
            
            # print(self.neighbors)
            # Initialize every link state valuje to 999 except for self, which is set to 0 
            self.link_state = [INFINITY] * total_nodes
            self.link_state[self.router_id] = 0
            # print(self.link_state)
            
            # Initialize correct cost for neighbors into link_state 
            for i in range(total_nodes):
                for j in self.neighbors_info.keys():
                    if i == j:
                        self.link_state[i] = self.neighbors_info[j][0]

            # print(self.link_state)
        except OSError as e:
            print(e)
            sys.exit()
  
    def get_node_amount(self):
        """
        Return the number of router nodes for network specified in config file

        Returns:
            int: number of nodes 
        """
        
        # Try to open file
        try:
            with open(self.config_file, 'r') as file:
                lines = file.readlines()
                return int(lines[0])
            
        # Raise error if file cannot open
        except OSError as e:
            print(e)
            sys.exit()
    
    def send_link_state_info(self):
        """
        Send link state information to all neighbors. Runs in a separate thread and continuously 
        sends the router's link state information to all neighbors.
        """
        id = -1
        
        # Get list of each neighbor's port
        for i in range(len(router_labels)):
            for j in self.neighbors_info.keys():
                if i == j:
                    self.neighbor_ports.append(self.neighbors_info[j][1])
                    
        while self.terminate_threads is not True:
            for i in range(len(self.link_state)):
                if int(self.link_state[i]) == 0:
                    id = i
                
            if id == -1:
                continue  
                         
            # Pickle link_state and send to each neighbor's port
            for port in self.neighbor_ports:
                new_link_state = [id, self.link_state]
                # print(f"new_link_state: {new_link_state}")
                data = pickle.dumps(new_link_state)
                self.sender_socket.sendto(data, (SERVERNAME, port))
                # print(f"SENT link_state TO PORT {port}")
                
            time.sleep(1)
            
    def receive_and_broadcast(self):
        """
        Receive link state information from neighbors and broadcast it. Runs in a separate thread 
        and continuously recieves link state information from neighbors and broadcasting it to other
        neighbors.
        """
        # Implement receiving link state information from one neighbor
        while self.terminate_threads is not True:
            
            data, addr = self.receiver_socket.recvfrom(4096)
            received_data = pickle.loads(data)
            if received_data == '':
                print("RECEIVED NOTHING")
            # print(f"received_data: {received_data}")
            
            flag = False
            c = 0 #Counter
            
            #Check if every id is in neighbors_data. If it is, stop receiving
            for i in range(len(router_labels)):
                if i in self.neighbors_data.keys():
                    c += 1
                    # print(f"c: {c}")
                if c == len(router_labels):
                    flag = True
                    # print("MADE FLAG TRUE")
            
            # Record received data in self.neighbors_data
            self.neighbors_data[received_data[0]] = received_data[1]
            # print(f"RECEIVED link_state FROM PORT {addr[1]}")
            # print(f"self.neighbors_data: {self.neighbors_data}")
            
            #Sends receieved data to neighbors
            for port in self.neighbor_ports:
                data = pickle.dumps(received_data)
                self.sender_socket.sendto(data, (SERVERNAME, port))
                # print(f"SENT link_state TO PORT {port}")
                
            if flag == True:
                # print("FLAG IS TRUE")
                self.received_all = True
                
            time.sleep(0.1) # SLeep for 0.1 sec so this function doesnt heat my laptop to 80C
            
            
    def dijkstra_algorithm(self):
        """
        Implement Dijkstra's algorithm to calculate shortest paths. Runs in a separate thread, 
        periodically calculating the shortest paths to all other nodes in the network using the 
        collected link state information.
        """
        while self.terminate_threads is not True:
            node_data = []
            self.path = []
            if self.received_all:
                # print(self.neighbors_data)
                
                # Add all the data from self.neighbors_data to node_data (in order)
                for i in range(len(router_labels)):
                    node_data.append(self.neighbors_data[i])
                    
                nodes = len(node_data[0])
                shortest_distances = [INFINITY] * nodes # Hold the shortest distance from self.router_id to i
                added = [False] * nodes

                # Initialize all distances as INFINITE
                for i in range(nodes):
                    shortest_distances[i] = INFINITY
                    added[i] = False

                shortest_distances[self.router_id] = 0 # Distance of suorce node from itself is 0
                parents = [-1] * nodes # Parent array to store the tree of shortest paths
                parents[self.router_id] = NO_PARENT 

                # Find the shortest path for all nodes
                for c in range(1, nodes):
                    # Pick the minimum distance node.
                    nearest_node = -1
                    shortest_distance = INFINITY
                    for j in range(nodes):
                        if not added[j] and shortest_distances[j] < shortest_distance:
                            nearest_node = j
                            # print(nearest_node)
                            shortest_distance = shortest_distances[j]

                    added[nearest_node] = True 

                    for k in range(nodes):
                        edge_distance = node_data[nearest_node][k]

                        if edge_distance > 0 and shortest_distance + edge_distance < shortest_distances[k]:
                            parents[k] = nearest_node
                            shortest_distances[k] = shortest_distance + edge_distance

                print("\n")
                self.print_result(shortest_distances, parents)
                print()
                self.print_forwarding_table()
                print("\n")


            time.sleep(10) 

    def print_result(self, shortest_distances, parents):
        """
        Print the result of Dijkstra's algorithm.

        Args:
            shortest_distances (list): List of shortest distances to each node.
            parents (list): List of parent nodes in the shortest path tree.
        """
        print("Desitantion_Routerid \t Distance \t Previous_node_id")
        self.prev_node = []
        self.next_node = []
        for i in range(len(shortest_distances)):

            self.get_path(i, parents)
            # print(f"self.path: {self.path}")
            if len(self.path) >= 2:
                self.prev_node.append(self.path[1])
                self.next_node.append(self.path[-2])
            else:
                self.prev_node.append(self.path[0])
                self.next_node.append(self.path[0])
            
            # print(f"i: {i}\tself.prev_node: {self.prev_node}\tself.next_node: {self.next_node}")

            print(f"{i}\t\t\t {shortest_distances[i]}\t\t {self.prev_node[i]}")
            self.path = []
        

    def get_path(self, current_node, parents):
        """
        Recursively construct the path from the source to the current node.

        Args:
            current_node (int): The current node being processed.
            parents (list): List of parent nodes in the shortest path tree.
        """
        
        # Base Case: If the current vertex is the source vertex
        if current_node == NO_PARENT:
            return
        self.path.append(current_node)
        self.get_path(parents[current_node], parents)
        
    def print_forwarding_table(self):
        """
        Prints the forwarding table for the router.
        """
        
        print("Desitantion_Routerid \t Next_hop_routerlabel")
        
        for i in range(len(router_labels)):
            # Do not print this router ID
            if i == self.router_id:
                continue
            print(f"{i}\t\t\t {router_labels[self.next_node[i]]}")

    def run(self):
        """
        Run the router simulation.
        """
        self.load_configuration()  # Load values from config file in object
        self.receiver_socket.bind(("", self.router_port))  # Bind socket to localhost and port from command line args
    
        send_link_state_thread = threading.Thread(target=self.send_link_state_info)
        receive_and_broadcast_thread = threading.Thread(target=self.receive_and_broadcast)
        dijkstra_algorithm_thread = threading.Thread(target=self.dijkstra_algorithm)
    
        try:
            # Start the threads
            send_link_state_thread.start()
            receive_and_broadcast_thread.start()
            dijkstra_algorithm_thread.start()
    
            # Wait for threads to finish (will only happen on keyboard interrupt)
            send_link_state_thread.join()
            receive_and_broadcast_thread.join()
            dijkstra_algorithm_thread.join()
    
        # Kill threads on keyboard interrupt
        except KeyboardInterrupt:
            self.terminate_threads = True
            send_link_state_thread.join()
            receive_and_broadcast_thread.join()
            dijkstra_algorithm_thread.join()
    
        # Close sockets
        finally:
            self.sender_socket.close()
            self.receiver_socket.close()
            print("Sockets closed.")  
   

if __name__ == "__main__":
    
    # Get args from CLI
    router_id = int(sys.argv[1])
    router_port = int(sys.argv[2])
    config_file = sys.argv[3]
    
    # Create new router
    router = Router(router_id, router_port, config_file)
    
    # Add uppercase letter as label for each router
    for i in range(router.get_node_amount()):
        router_labels.append(ALPHABET[i])
    
    # Run router
    router.run()
    