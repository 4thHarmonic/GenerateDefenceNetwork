import numpy as np
import pandas as pd
import os
from utilities import read_sheet, fill_edges, fill_nodes, save_file, find_latest_input_file
from polinode import generate_network


# This converts a spreadsheet into a network for Polinode.
# It then saves it and uploads it to Polinode

val_cols = ['Total spending in $B', 'Spending 2021-25 in $B', 'Spending 2026-30 in $B', 'Spending 2031-35 in $B',
            'Spending 2036-40 in $B']


def read_nodes(sheet):
    nodes = read_sheet(input_file, sheet, val_cols=val_cols)
    nodes['Node Type'] = sheet
    return nodes


def add_vals(sheet, df, overview):
    """Add time phased project values to a type of nodes"""
    vals = pd.pivot_table(overview, index=sheet, values=val_cols, aggfunc=np.sum)
    df = df.merge(vals, left_on='Name', right_index=True)
    return df


def calculate_sic_flows(overview):
    """Calculate the flows of sic funding from each program by period"""
    num_sic_col = 'Number of SICs'

    def calc_num_sics(row):
        num_sics = 0
        for sic in ['SIC 1', 'SIC 2', 'SIC 3']:
            if type(row[sic]) is str:
                num_sics += 1
        return num_sics

    overview[num_sic_col] = overview.apply(calc_num_sics, axis=1)
    # find the sic values
    shares = pd.DataFrame([[0.00, 0.00, 0.00],
                           [1.00, 0.00, 0.00],
                           [0.60, 0.40, 0.00],
                           [0.50, 0.35, 0.15]], columns=['SIC 1', 'SIC 2', 'SIC 3'])

    def create_sum(row, share_col):
        num_sics = row[num_sic_col]
        share = share_col[num_sics]
        aic = row['AIC as % of Total']
        sic = row['SIC as % of AIC']
        tot = row['ToT as % of Total']
        all_aic = aic * sic + tot
        for fund_val in val_cols:
            row[fund_val] = row[fund_val] * share * all_aic
        return row

    # create a copy for each SIC
    sic1 = overview.copy()
    sic2 = overview.copy()
    sic3 = overview.copy()
    # calculate SIC value
    sic1 = sic1.apply(create_sum, axis=1, args=(shares['SIC 1'],))
    sic2 = sic2.apply(create_sum, axis=1, args=(shares['SIC 2'],))
    sic3 = sic3.apply(create_sum, axis=1, args=(shares['SIC 3'],))
    # group the values by sic and prime
    sic1_sum = pd.pivot_table(sic1, index=['SIC 1', 'Prime Contractor'], values=val_cols, aggfunc=np.sum).reset_index()
    sic2_sum = pd.pivot_table(sic2, index=['SIC 2', 'Prime Contractor'], values=val_cols, aggfunc=np.sum).reset_index()
    sic3_sum = pd.pivot_table(sic3, index=['SIC 3', 'Prime Contractor'], values=val_cols, aggfunc=np.sum).reset_index()
    # fix the cols
    sic1_sum = sic1_sum.rename(columns={'SIC 1': 'SIC'})
    sic2_sum = sic2_sum.rename(columns={'SIC 2': 'SIC'})
    sic3_sum = sic3_sum.rename(columns={'SIC 3': 'SIC'})
    # add the values of the three SICs
    sic_vals = pd.concat([sic1_sum, sic2_sum, sic3_sum])
    sic_sum = pd.pivot_table(sic_vals, index=['SIC', 'Prime Contractor'], values=val_cols, aggfunc=np.sum).reset_index()
    return sic_sum


def read_inputs():
    """Read the spreadsheet info and create nodes and dfs"""
    overview = read_sheet(input_file, 'Overview', val_cols=val_cols)
    # node inputs
    md = read_nodes('Military Domain')
    md['Military Domain'] = md['Name']
    md = add_vals('Military Domain', md, overview)

    mc = read_nodes('Military Capability')
    mc = add_vals('Military Capability', mc, overview)

    col: str = "Program, Platform or System"
    pps = overview[[col, 'Total spending in $B', 'Spending 2021-25 in $B', 'Spending 2026-30 in $B',
                    'Spending 2031-35 in $B', 'Spending 2036-40 in $B', 'Military Domain',
                    'Product Number (Generally a Sustainment Activity)',
                    'Program Number (Generally an Acquisition Activity)']].copy()
    pps = pps[pps[col].notna()]
    pps["Node Type"] = col
    pps["Name"] = pps[col]
    pps = pps.rename(columns={col: "Description"})
    pps = pps.drop_duplicates(['Name'])

    pc = read_nodes('Prime Contractor')
    pc = add_vals('Prime Contractor', pc, overview)

    sicp = read_nodes('Sovereign Industry Capability')
    sic_sum = calculate_sic_flows(overview)
    sic_only = pd.pivot_table(sic_sum, index='SIC', aggfunc=np.sum)
    sicp = pd.merge(sicp, sic_only, left_on='Name', right_index=True)

    ss = read_nodes('DSTG STaR Shot')

    nodes = pd.concat([md, mc, pps, pc, sicp, ss])
    return nodes, overview, ss, sic_sum


def format_edges(df, s_col, t_col):
    """format two cols in df as a df of edges"""
    new_edges = df[[s_col, t_col]].copy()
    new_edges = new_edges[new_edges[s_col].notna()]
    new_edges = new_edges[new_edges[t_col].notna()]
    new_edges = new_edges[~new_edges[s_col].isin([False, 0, 'false'])]
    new_edges = new_edges[~new_edges[t_col].isin([False, 0, 'false'])]
    new_edges = new_edges.rename(columns={s_col: "Source", t_col: "Target"})
    new_edges = new_edges.drop_duplicates()
    new_edges = new_edges.copy()
    new_edges["Edge Type"] = "Link from " + s_col + " to " + t_col
    return new_edges


def create_edges(overview, ss):
    """create the base edges"""
    #  from overview
    md_mc = format_edges(overview, "Military Domain", "Military Capability")
    mc_p = format_edges(overview, "Military Capability", "Program, Platform or System")
    p_pc = format_edges(overview, "Program, Platform or System", "Prime Contractor")
    # Create edges between SSs and SICPs
    sic1 = format_edges(ss, 'Name', 'SIC 1')
    sic1['Edge Type'] = 'Link from STaR Shot to primary SIC'
    sic2 = format_edges(ss, 'Name', 'SIC 2')
    sic2['Edge Type'] = 'Link from STaR Shot to secondary SIC'
    sic3 = format_edges(ss, 'Name', 'SIC 3')
    sic3['Edge Type'] = 'Link from STaR Shot to tertiary SIC'
    #
    edges = pd.concat([md_mc, mc_p, p_pc, sic1, sic2, sic3])
    return edges


def create_prime_flows(overview, target):
    """Create the project flows to a target part of a prime supply chain"""
    summary = overview.copy()

    def calc_val(row):
        split = row[target]
        for col in val_cols:
            row[col] = row[col] * split
        return row

    summary = summary.apply(calc_val, axis=1)
    flow = pd.pivot_table(summary, index='Prime Contractor', values=val_cols, aggfunc=np.sum)
    return flow.reset_index()


def create_prime_networks(nodes, edges, overview, sic_sum):
    """create nodes and edges for the prime supply chains to SICs"""
    # create the additional targets needed on overview
    overview['Foreign as % of Total'] = 1 - overview['AIC as % of Total']
    overview['SIC as % of Total'] = overview['AIC as % of Total'] * overview['SIC as % of AIC']
    # create nodes: Aus Supply Chain
    aic_nodes = create_prime_flows(overview, 'AIC as % of Total')
    aic_nodes['Name'] = "Australian supply chain for " + aic_nodes['Prime Contractor']
    aic_nodes['Description'] = aic_nodes['Prime Contractor'] + " Australian supply chain (AIC)"
    aic_nodes['Node Type'] = 'Australian supply chain (AIC)'
    # create nodes: OS Supply Chain
    os_nodes = create_prime_flows(overview, 'Foreign as % of Total')
    os_nodes['Name'] = "Overseas supply chain for " + os_nodes['Prime Contractor']
    os_nodes['Description'] = os_nodes['Prime Contractor'] + " Overseas supply chain"
    os_nodes['Node Type'] = 'Overseas supply chain'
    # create nodes: ToT (not visualised in this version)
    tot_nodes = create_prime_flows(overview, 'ToT as % of Total')
    tot_nodes['Name'] = "ToT commitments for " + tot_nodes['Prime Contractor']
    tot_nodes['Description'] = 'Transfers of technology facilitated by' + tot_nodes['Prime Contractor']
    tot_nodes['Node Type'] = 'Prime commitments to ToT'
    tot_nodes['Source'] = "Overseas supply chain for " + os_nodes['Prime Contractor']
    tot_nodes['Target'] = "SIC commitments for " + os_nodes['Prime Contractor']
    # create nodes: Prime SIC
    sic_nodes = create_prime_flows(overview, 'SIC as % of Total')
    sic_nodes['Name'] = "SIC commitments for " + sic_nodes['Prime Contractor']
    sic_nodes['Description'] = 'SIC facilitated by ' + sic_nodes['Prime Contractor'] + " inc. ToT"
    sic_nodes['Node Type'] = 'Prime commitments to SIC'
    sic_nodes['Source'] = "Australian supply chain for " + sic_nodes['Prime Contractor']
    # add nodes
    nodes = pd.concat([nodes, aic_nodes, os_nodes, sic_nodes])
    # create edges: prime --> aic
    aic_edges = aic_nodes.copy()
    aic_edges['Edge Type'] = 'Funds spent in Australia'
    aic_edges['Description'] = 'Funds deployed in Australia by ' + aic_edges['Prime Contractor']
    aic_edges = aic_edges.rename(columns={'Prime Contractor': 'Source', 'Name': 'Target'})
    # create edges:  prime --> os
    os_edges = os_nodes.copy()
    os_edges['Edge Type'] = 'Funds deployed overseas'
    os_edges['Description'] = 'Funds deployed overseas by ' + os_edges['Prime Contractor']
    os_edges = os_edges.rename(columns={'Prime Contractor': 'Source', 'Name': 'Target'})
    # create edges:  aic --> sic
    sic_edges = sic_nodes.copy()
    sic_edges['Edge Type'] = 'Funds deployed against SIC from Aus supply chain'
    sic_edges['Description'] = 'Funds deployed for SIC by ' + sic_edges['Prime Contractor']
    sic_edges = sic_edges.rename(columns={'Name': 'Target'})
    # create edges: os --> SIC (i.e. ToT)
    tot_edges = tot_nodes.copy()
    tot_edges['Edge Type'] = 'Funds deployed against SIC from Overseas via ToT'
    tot_edges['Description'] = 'Funds deployed for ToT by ' + tot_edges['Prime Contractor']
    # create edges: Prime SIC --> SIC
    sic_sum['Source'] = "SIC commitments for " + sic_sum['Prime Contractor']
    sic_sum = sic_sum.rename(columns={'SIC': 'Target'})
    sic_sum['Edge Type'] = 'Prime commitments to a particular SIC'
    # add edges
    edges = pd.concat([edges, aic_edges, os_edges, sic_edges, tot_edges, sic_sum])
    return nodes, edges


def format_network(nodes, edges):
    """Prepare the network"""
    nodes = fill_nodes(nodes, val_cols)
    edges = fill_edges(edges)
    # adjust duplicate program nodes to be shared effectors
    shared_caps = ['ISR', 'GBAD', 'Munitions Procurement and Manufacture']
    nodes.loc[nodes['Name'].isin(shared_caps), 'Node Type'] = 'Shared effector'
    cols = ['Name', 'Node Type']
    nodes = nodes.drop_duplicates(subset=cols)
    # Create network labels for defence overview
    nodes['Defence Overview Label'] = nodes['Name']
    label = ['Prime Contractor', 'Sovereign Industry Capability', 'Military Domain']
    nodes.loc[~nodes['Node Type'].isin(label), 'Defence Overview Label'] = ' '
    # strip excess fields
    nodes = nodes.drop(['SIC 1', 'SIC 2', 'SIC 3', 'Source', 'Target'], axis=1, errors='ignore')
    edges = edges.drop(['Node Type', 'Name', 'Description', 'Prime Contractor'], axis=1)
    # set values
    nodes['Size'] = nodes['Total spending in $B']
    edges['Weight'] = edges['Total spending in $B']

    return nodes, edges


def create_national_model():
    """Generate the national defence model for Polinode"""
    nodes, overview, ss, sic_sum = read_inputs()
    edges = create_edges(overview, ss)
    nodes, edges = create_prime_networks(nodes, edges, overview, sic_sum)
    nodes, edges = format_network(nodes, edges)
    return nodes, edges


if __name__ == '__main__':
    # find the latest version of the file
    core_file = 'Overall defence capability ecosystem v.1('
    input_file = find_latest_input_file(core_file)
    # generate the model
    nat_nodes, nat_edges = create_national_model()
    # save to excel
    data_path = '/home/charles/Desktop'
    output_file = os.path.join(data_path, 'National Defence for Polinode v2.xlsx')
    save_file(nat_nodes, nat_edges, output_file)
    # if upload_model_to_polinode()
    network_name = 'Charles Test 4'
    network_desc = 'Test the API'
#    generate_network(network_name, network_desc, nodes, edges)
