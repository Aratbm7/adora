from rest_framework import permissions
from django.shortcuts import get_object_or_404
from django.db.models import Q
from math import log2
from collections import defaultdict

action_dict = {
    'retrieve': 1,
    'list': 2,
    'partially_update': 4,
    'update': 8,
    'create': 16,
    'destroy': 32,
    # for all 63
}

 
def return_view_action_lists(mask):
    if mask == 0:
        return []
    x = int(log2(mask + 1))
    return tuple(action_dict.keys())[:x]


def personal_permissions(input_dict):
    send_dict = defaultdict(lambda: 63)
    # print(send_dict)
    send_dict.update(input_dict)

    class CustomPermisson(permissions.BasePermission):

        def has_permission(self, request, view):
            user_permisson_list = return_view_action_lists(send_dict['u'])
            admin_permisson_list = return_view_action_lists(send_dict['a'])
            other_permisson_list = return_view_action_lists(send_dict['o'])
            
            if  request.user and request.user.is_superuser:
                return True

            if request.user and request.user.is_authenticated:
                if view.action in user_permisson_list:
                    return True

            elif request.user.is_staff:
                if view.action in admin_permisson_list:
                    return True

            elif not request.user.is_authenticated:
                if view.action in other_permisson_list:
                    return True

            return False
    return CustomPermisson



def object_level_permissions(input_dict):
    # Default all roles to full permissions (63)
    send_dict = defaultdict(lambda: 63)
    send_dict.update(input_dict)

    # Define the custom object-level permission class
    class CustomObjectPermission(permissions.BasePermission):

        def has_object_permission(self, request, view, obj):
            # Generate allowed actions for each user type at the object level
            user_permission_list = return_view_action_lists(send_dict['u'])
            admin_permission_list = return_view_action_lists(send_dict['a'])
            other_permission_list = return_view_action_lists(send_dict['o'])
            
            if  request.user and request.user.is_superuser:
                    return True
                
            if request.user and request.user.is_authenticated:
                # If user is admin, grant full access
                if request.user.is_staff  or request.user.is_superuser:
                    if view.action in admin_permission_list:
                        return True
                else:
                    # Check if the action is allowed and the user owns the object
                    if view.action in user_permission_list and obj.user == request.user:
                        return True
            else:
                # Allow read-only access for others if permitted
                if view.action in other_permission_list and view.action in ['retrieve', 'list']:
                    return True

            return False

    return CustomObjectPermission


#‌ In this permission class just restricted actions for authenticated user for 
# object level permissions is update partial_update and destroyed
#‌ this mean user can be retrieve and list other objects but can't be changes or deletes them
def object_level_permissions_restricted_actions(input_dict):
    send_dict = defaultdict(lambda: 63)
    send_dict.update(input_dict)

    class CustomObjectPermission(permissions.BasePermission):

        def has_object_permission(self, request, view, obj):
            user_permission_list = return_view_action_lists(send_dict['u'])
            admin_permission_list = return_view_action_lists(send_dict['a'])
            other_permission_list = return_view_action_lists(send_dict['o'])

            restricted_actions = ['update', 'partial_update', 'destroy']
            
            if  request.user and request.user.is_superuser:
                return True

            if request.user and request.user.is_authenticated:
                
                
                if request.user.is_staff:
                    if view.action in admin_permission_list:
                        return True
                else:
                    if view.action in restricted_actions:
                        if view.action in user_permission_list and obj.user == request.user:
                            return True
                    else:
                        if view.action in user_permission_list:
                            return True
            else:
                if view.action in other_permission_list and view.action in ['retrieve', 'list']:
                    return True

            return False

    return CustomObjectPermission


def address_object_level_permissions(input_dict):
    # Default all roles to full permissions (63)
    send_dict = defaultdict(lambda: 63)
    send_dict.update(input_dict)

    # Define the custom object-level permission class
    class CustomObjectPermission(permissions.BasePermission):

        def has_object_permission(self, request, view, obj):
            # Generate allowed actions for each user type at the object level
            user_permission_list = return_view_action_lists(send_dict['u'])
            admin_permission_list = return_view_action_lists(send_dict['a'])
            other_permission_list = return_view_action_lists(send_dict['o'])
            
            if  request.user and request.user.is_superuser:
                    return True
                
            if request.user and request.user.is_authenticated:
                # If user is admin, grant full access
                if request.user.is_staff  or request.user.is_superuser:
                    if view.action in admin_permission_list:
                        return True
                else:
                    # Check if the action is allowed and the user owns the object
                    if view.action in user_permission_list and obj.profile.user == request.user:
                        return True
            else:
                # Allow read-only access for others if permitted
                if view.action in other_permission_list and view.action in ['retrieve', 'list']:
                    return True

            return False

    return CustomObjectPermission
