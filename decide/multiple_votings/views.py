from voting.models import Voting
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.db import IntegrityError
from .forms import BaseVotingForm

def home(request):
    return render(request, 'home.html')


def signup(request):
    if request.method == 'GET':
        return render(request, 'signup.html',
                      {'form': UserCreationForm})
    else:
        if (request.POST['password1'] == request.POST['password2']):
            try:
                user = User.objects.create_user(username=request.POST['username'],
                                                password=request.POST['password1'])
                user.save()
                login(request, user)
                return redirect('list_votings')
            except IntegrityError:
                return render(request, 'signup.html',
                              {'form': UserCreationForm(),
                               "error": 'username already taken'})

        return render(request, 'signup.html',
                      {'form': UserCreationForm(),
                       "error": 'passwords did not match'})


def signin(request):
    if request.method == 'GET':
        return render(request, 'signin.html', {
            'form': AuthenticationForm
        })
    else:
        user = authenticate(
            request, username=request.POST['username'], password=request.POST['password'])
        if user is None:
            return render(request, 'signin.html', {
                'form': AuthenticationForm(),
                'error': 'username or password is incorrect'
            })
        else:
            login(request, user)
            if user.is_superuser:
                return redirect('multiple_votings')
            return redirect('list_votings')


def multiple_votings(request):
    if request.method == 'GET':
        return render(request, 'multiple_votings.html',{
            'form': BaseVotingForm
        })
    else:
        try:
            form =BaseVotingForm(request.POST)
            new_voting = form.save(commit=False)
            new_voting.save()
            print(new_voting)
            return render(request, 'multiple_votings.html',{
                'form': BaseVotingForm
            })
        except :
            return render(request, 'multiple_votings.html',{
                'form': BaseVotingForm,
                'error': 'Bad data',
            })

def list_votings(request):
    votings = Voting.objects.all()
    return render(request, 'list_votings.html',{
        'votings': votings
    })

def signout(request):
    logout(request)
    return redirect('home')