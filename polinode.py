import os.path

import requests
import pprint
from utilities import read_nodes, read_edges
from my_credentials import username, password


def convert_dfs_json(nodes, edges):
    """read a Polinode Excel file and return its Json equivalent"""
    node_attributes = nodes.to_dict(orient='records')
    node_data = []
    for node in node_attributes:
        node_id = node['Name']
        node_data.append({'id': node_id, 'attributes': node})
    edge_attributes = edges.to_dict(orient='records')
    edge_data = []
    count = 0
    for edge in edge_attributes:
        source = edge['Source']
        target = edge['Target']
        del edge['Source']
        del edge['Target']
        edge_data.append({'id': count, 'source': source, 'target': target, 'attributes': edge})
        count += 1
    network_info = {'nodes': node_data, 'edges': edge_data}
    return network_info


def find_networks():
    """ Retrieving a summary of all networks for a user."""
    r = requests.get('https://app.polinode.com/api/v2/networks',
                     auth=(username, password))
    networks = r.json()
    print(len(networks), ' networks were found at Polinode')
    return networks


def create_network(name, description, network_data, directed=True):
    """Create a network"""
    r = requests.post('https://app.polinode.com/api/v2/networks',
                      auth=(username, password),
                      json={'name': name,
                            'networkJSON': network_data,
                            'status': 'Private',
                            'fileType': 'JSON',
                            'originalFileType': 'JSON',
                            'isDirected': directed,
                            'description': description})
    network = r.json()
    print('Summary of network created:')
    pprint.pprint(network, indent=2)


def update_network(name, description, network_data, network_id):
    """Update an existing network on Polinode"""

    r = requests.put('https://app.polinode.com/api/v2/networks/' + network_id,
                     auth=(username, password),
                     json={'name': name,
                           'description': description,
                           'networkJSON': network_data})
    network = r.json()
    print('Summary of updated network:')
    pprint.pprint(network, indent=2)


def generate_network(name, description, nodes, edges, directed=True):
    """Check if network exists and create or update as appropriate"""
    # Check for network
    polinode_networks = find_networks()
    present = False
    network_id = ""
    for network in polinode_networks:
        if network['name'] == name:
            present = True
            network_id = network['_id']
            continue
    # convert the data to a JSON file
    network_data = convert_dfs_json(nodes, edges)
    # create or update the network
    if present:
        print(name, ' WAS present, and has been updated.')
        update_network(name, description, network_data, network_id)
    else:
        print(name, ' WAS NOT present, and has been created.')
        create_network(name, description, network_data, directed)


if __name__ == '__main__':
    # get nodes and edges
    data_path = '/home/charles/Desktop'
    input_filename = 'National Defence for Polinode.xlsx'
    file_path = os.path.join(data_path, input_filename)
    net_nodes = read_nodes(file_path)
    net_edges = read_edges(file_path, 'Edges')
    # generate the network
    network_name = 'Charles Test 3'
    network_desc = 'Test the API'
    generate_network(network_name, network_desc, net_nodes, net_edges)
