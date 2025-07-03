import networkx as nx
import matplotlib.pyplot as plt

# Visualizing course graph
def flatten_graph_dict(graph_dict):
    edges = []
    print(graph_dict)
    for prereq, courses in graph_dict.items():
        for course in courses:
            edges.append((prereq, course))
    return edges

def visualize_graph(flattened_graph_edges, all_courses):
    G = nx.DiGraph()
    G.add_edges_from(flattened_graph_edges)

    # Add isolated nodes explicitly
    G.add_nodes_from(all_courses)

    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(G, seed=1)
    nx.draw(
        G, pos,
        with_labels=True,
        arrows=True,
        node_color='lightblue',
        edge_color='gray',
        node_size=100,
        font_size=10,
        font_weight='bold'
    )
    plt.show()
