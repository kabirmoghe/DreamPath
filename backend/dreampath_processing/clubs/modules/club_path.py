from dataclasses import dataclass

from dreampath_processing.clubs.modules.activity import Activity


@dataclass
class ClubPath:
    recommendations: dict[str, Activity]

    def remove_activity(self, activity_slug: str):
        if activity_slug not in self.recommendations:
            raise ValueError(f"Cannot remove activity with slug '{activity_slug}', not in ClubPath.")
        self.recommendations.pop(activity_slug)

    def add_activity(self, activity: Activity):
        slug = activity.activity_slug
        if slug in self.recommendations:
            raise ValueError(f"Cannot add activity with slug '{slug}', already in ClubPath.")
        self.recommendations[slug] = activity

    def __str__(self) -> str:
        if not self.recommendations:
            return "No activities."
        lines = []
        for i, (slug, activity) in enumerate(self.recommendations.items(), 1):
            params = ", ".join(sorted(activity.aligned_parameters)) if activity.aligned_parameters else "none"
            parts = [f"{i}. {activity.display_name} ({slug}) — aligned: {params}"]
            if activity.membership_status and activity.membership_status != "not_yet_joined":
                parts.append(f"status: {activity.membership_status}")
            if activity.current_role:
                parts.append(f"role: {activity.current_role}")
            if activity.roles_exposed:
                parts.append(f"available roles: {', '.join(activity.roles_exposed)}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def reorder_activity(self, activity_slug: str, position: int):
        """Move an activity to a specific position (0-indexed) in the ranked list."""
        if activity_slug not in self.recommendations:
            raise ValueError(f"Cannot reorder activity with slug '{activity_slug}', not in ClubPath.")
        activity = self.recommendations.pop(activity_slug)
        items = list(self.recommendations.items())
        items.insert(position, (activity_slug, activity))
        self.recommendations = dict(items)
