import pandas as pd
import os


def clean_val(val):
    """Clean an input data value"""
    if type(val) is str:
        val = val.rstrip()
    return val


def read_sheet(file_address, sheet, val_cols=[], col_types={}, rows_to_skip=0):
    """ Read a file sheet to create a df. """
    df = pd.read_excel(file_address,
                       sheet_name=sheet,
                       converters=col_types,
                       skiprows=rows_to_skip,
                       index_col=None)
    for col in df.columns:
        df[col] = df[col].apply(clean_val)
        if col in val_cols:
            df[col] = df[col].fillna(0)

    return df


def fill_nodes(nodes):
    """Fill in gaps in nodes"""
    node_val_cols = ['Total spending in $B', 'Spending 2021-25 in $B', 'Spending 2026-30 in $B',
                     'Spending 2031-35 in $B', 'Spending 2036-40 in $B']
    nodes[node_val_cols] = nodes[node_val_cols].fillna(0)
    nodes = nodes.fillna('')
    return nodes


def read_nodes(file_address, nodes_sheet='Nodes', col_types={}, rows_to_skip=0):
    """ Read a file to create a nodes df. """
    nodes = read_sheet(file_address, nodes_sheet, col_types, rows_to_skip)
    nodes = fill_nodes(nodes)
    return nodes


def fill_edges(edges):
    """Fill in gaps"""
    edges = edges.fillna('')
    return edges


def read_edges(file_address, edges_sheet='Edges', col_types={}, rows_to_skip=0):
    """ Read a file sheet to create an edges df. """
    edges = read_sheet(file_address, edges_sheet, col_types, rows_to_skip)
    edges = fill_edges(edges)
    return edges


def find_latest_input_file(filename):
    """Get the latest version of the input file from downloads"""
    download_path = '/home/charles/Downloads'
    versions = {}
    contents = os.listdir(download_path)
    excel = [f for f in contents if 'xlsx' in f]
    for file in excel:
        if filename in file:
            val = file[(file.find('(') + 1):file.find(')')]
            val = int(val)
            versions[val] = file
    file = versions[max(versions)]
    print('Using input file: ', file)
    return os.path.join(download_path, file)


def save_file(nodes, edges, file_address):
    """ Saves a network as a file. """
    # Create a Pandas Excel writer using XlsxWriter as the engine.
    writer = pd.ExcelWriter(file_address, engine='xlsxwriter')

    # Write each dataframe to a different worksheet.
    nodes.to_excel(writer, sheet_name='Nodes', index=False)
    edges.to_excel(writer, sheet_name='Edges', index=False)
    # Close the Pandas Excel writer and output the Excel file.
    writer.save()
    print('A new excel file was saved as ', file_address)
