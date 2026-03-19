from rest_framework.permissions import BasePermission

from .models import CircleMembership


class IsCircleMember(BasePermission):
    def has_permission(self, request, view):
        circle_id = view.kwargs.get('circle_id')
        if not request.user or not request.user.is_authenticated or not circle_id:
            return False
        return CircleMembership.objects.filter(circle_id=circle_id, user=request.user).exists()


class IsCircleOwner(BasePermission):
    def has_permission(self, request, view):
        circle_id = view.kwargs.get('circle_id')
        if not request.user or not request.user.is_authenticated or not circle_id:
            return False
        return CircleMembership.objects.filter(
            circle_id=circle_id,
            user=request.user,
            role=CircleMembership.Role.OWNER,
        ).exists()
