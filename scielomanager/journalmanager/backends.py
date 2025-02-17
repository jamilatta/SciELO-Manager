# -*- encoding: utf-8 -*-
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


from journalmanager import models

class ModelBackend(ModelBackend):
    """
    Authenticate against the DJANGO login or user e-mail

    Use the login name, and password or userprofile.email and password
    """

    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            try:
                userprofile = models.UserProfile.objects.get(email=username)
                if userprofile.user.check_password(password):
                    return userprofile.user
            except models.UserProfile.DoesNotExist:
                return None

        return None


    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
