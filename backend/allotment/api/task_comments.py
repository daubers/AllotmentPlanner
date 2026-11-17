from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import events
from ..extensions import db
from ..models import Role, Task, TaskComment, TaskStatus, User
from ..schemas import TaskCommentInSchema, TaskCommentPatchSchema, TaskCommentSchema
from ..security import require_role
from .tasks import _finish, _reopen
from .tasks import _get as _get_task

blp = Blueprint(
    "task_comments",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/tasks/<int:task_id>/comments",
    description="Timestamped comments on a task, each able to report a status",
)


def _get(allotment, task: Task, comment_id: int) -> TaskComment:
    comment = db.session.get(TaskComment, comment_id)
    if comment is None or comment.task_id != task.id or comment.allotment_id != allotment.id:
        abort(404, message="Comment not found")
    return comment


def comment_to_dict(comment: TaskComment) -> dict:
    author = db.session.get(User, comment.created_by) if comment.created_by else None
    return {
        "id": comment.id,
        "task_id": comment.task_id,
        "body": comment.body,
        "status": comment.status,
        "progress": comment.progress,
        "author": author.display_name if author else None,
        "author_id": comment.created_by,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        # created_at and updated_at are set a few microseconds apart on insert.
        "edited": (comment.updated_at - comment.created_at).total_seconds() > 1,
    }


def _apply_status(task: Task, status: str, allotment, membership) -> list[tuple[str, dict]]:
    """Move ``task`` to ``status`` the way the task endpoints do; returns the events to emit."""
    if task.status == status:
        return []
    subject = {"task_id": task.id, "feature_id": task.feature_id}
    if status == TaskStatus.DONE:
        spawned = _finish(task, allotment, membership)
        db.session.flush()
        return [
            (
                "task.completed",
                {
                    "subject": subject,
                    "payload": {
                        "title": task.title,
                        "spawned_task_id": spawned.id if spawned else None,
                    },
                },
            )
        ]
    was_done = task.status == TaskStatus.DONE
    if was_done:
        _reopen(task)
    task.status = status
    if was_done:
        return [("task.reopened", {"subject": subject, "payload": {}})]
    return [("task.updated", {"subject": subject, "payload": {"fields": ["status"]}})]


@blp.route("")
class TaskComments(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TaskCommentSchema(many=True))
    def get(self, allotment, membership, task_id):
        """Comments on a task, oldest first."""
        task = _get_task(allotment, task_id)
        comments = (
            db.session.query(TaskComment)
            .filter_by(task_id=task.id)
            .order_by(TaskComment.created_at, TaskComment.id)
            .all()
        )
        return [comment_to_dict(c) for c in comments]

    @require_role(Role.EDITOR)
    @blp.arguments(TaskCommentInSchema)
    @blp.response(201, TaskCommentSchema)
    def post(self, data, allotment, membership, task_id):
        """Add a comment. With a `status` the task moves to it in the same step."""
        task = _get_task(allotment, task_id)
        status = data.get("status")
        queued = _apply_status(task, status, allotment, membership) if status else []
        comment = TaskComment(
            allotment_id=allotment.id,
            task_id=task.id,
            body=(data.get("body") or "").strip(),
            status=status,
            progress=(data.get("progress") or "").strip() or None,
            created_by=membership.user_id,
        )
        db.session.add(comment)
        db.session.commit()
        for name, extra in queued:
            events.emit(name, actor_id=membership.user_id, allotment_id=allotment.id, **extra)
        events.emit(
            "task.comment_added",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "comment_id": comment.id},
            payload={"status": status},
        )
        return comment_to_dict(comment)


@blp.route("/<int:comment_id>")
class TaskCommentView(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(TaskCommentPatchSchema)
    @blp.response(200, TaskCommentSchema)
    def patch(self, data, allotment, membership, task_id, comment_id):
        """Change the text or progress label. Only the author can; the status it set stays."""
        comment = _get(allotment, _get_task(allotment, task_id), comment_id)
        if comment.created_by != membership.user_id:
            abort(403, message="Only the author can edit a comment")
        if "body" in data:
            comment.body = data["body"].strip()
        if "progress" in data:
            comment.progress = (data["progress"] or "").strip() or None
        if not comment.body and not comment.status and not comment.progress:
            abort(422, message="A comment needs some text, a status or a progress label")
        db.session.commit()
        events.emit(
            "task.comment_updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": comment.task_id, "comment_id": comment.id},
            payload={},
        )
        return comment_to_dict(comment)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, task_id, comment_id):
        """Delete a comment: its author, or an owner of the allotment."""
        comment = _get(allotment, _get_task(allotment, task_id), comment_id)
        if comment.created_by != membership.user_id and membership.role != Role.OWNER:
            abort(403, message="Only the author or an owner can delete a comment")
        subject = {"task_id": comment.task_id, "comment_id": comment.id}
        db.session.delete(comment)
        db.session.commit()
        events.emit(
            "task.comment_deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject=subject,
            payload={},
        )
