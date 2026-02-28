from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect("messaging:index")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next", "messaging:index"))
    return render(request, "core/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("core:login")


@login_required
def profile_view(request):
    return render(request, "core/profile.html")
