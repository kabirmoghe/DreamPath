"""DreamPath Agent - Course path planning and academic advising."""

from dreampath_processing.dreampath_agent.graph import build_dreampath_graph

# Build and export compiled graph (without checkpointer - provided at runtime by service layer)
dreampath_agent = build_dreampath_graph(checkpointer=None)
dreampath_agent.name = "dreampath-agent"
