> works now! Can you describe to me how the current streaming behavior works? It doesn't seem like the end output is truly being streamed, as it appears all in one blob.
  Ultimately, I want to stream nodes as follows to show users what's going on behind the scenes (don't want to implement yet but want to get your feedback): \
  \
  Orchestrator --> Show as Thinking with dynamic ellipses\
  CourseSearch--> Searching Dartmouth Courses w/ elipses (with the 'reason' from the orchestrator showing up in a small collapsable beneath it)\
  ModifyProfile --> Modifying Profile w/ elipses (same)\
  PlanBuilder --> Planning CoursePath Modifications
  CoursePath --> Executing Modifications (same); would also be great to maybe take advantage of structured output to show the diff presented from the CPAgent as a nice git-like
  diff with green/red/gray coloration for add/remove/move visualization clarity), maybe with a confirm/cancel button that automatically handles confirm/cancel from user, or
  with the option for suggesting changes below in the textbox)\
  RebuildCoursePath --> Rebuilding CoursePath (...), would be nice to also somehow stream the steps along the way, like modifying profile, searching for courses, updating
  course recommendations, etc. along the way (right now, like the behavior just from print statements via CLI agent, but could be cool to replicate in UI).\
  Finalize --> Finalizing... 