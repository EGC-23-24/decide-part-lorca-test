from rest_framework.response import Response
from django.http import HttpResponse
from rest_framework.status import (
        HTTP_201_CREATED,
        HTTP_200_OK,
        HTTP_400_BAD_REQUEST,
        HTTP_401_UNAUTHORIZED
)
from django.http import HttpRequest, QueryDict
from django.contrib.auth import logout
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import obtain_auth_token
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import ObjectDoesNotExist
from django.template import loader
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django import forms
from .serializers import UserSerializer
from django.core.exceptions import ValidationError  
from django.forms.fields import EmailField  
from django.forms.forms import Form 
import re
from django.contrib.auth import authenticate, login
from django.core.mail import EmailMessage
from django.shortcuts import render
from census.models import Census
from voting.models import Voting

class CustomUserCreationForm(UserCreationForm):  

    class Meta(UserCreationForm.Meta):
        model = User
        fields= (
            'username',
            'password1',
            'password2',
            'email',
            'first_name',
            'last_name'
        )

        labels = {
            'username':('Username'),
            'password1':('Password'),
            'password2':('Confirm Password'),
            'email':('Email'),
            'first_name':('First Name'),
            'last_name':('Last Name')
        }
  
    def username_clean_lenght(self, username):  
        username = username.lower()  

        if len(username) > 150:
            return True
        else:
            return False
        

    def username_clean_exits(self, username):
        username = username.lower()

        new = User.objects.filter(username = username)  
        if new.count():  
            return True
        else:
            return False

    def username_clean_pattern(self, username):
        username = username.lower()

        username_val_regex = re.search("[^\w@.\-_+]", username)
        if(username_val_regex != None):
            return True
        return False
  
    def email_clean(self,email):  
        email = email.lower()  
        new = User.objects.filter(email=email)  
        if new.count():  
            return True
        return False
  
    def clean_confirmation(self, password, confirm_password): 
        if password and confirm_password and password != confirm_password:  
            return True
        return False
    
    def clean_password_lenght(self, password):
        if len(password)<8:
            return True
        else:
            return False

    def clean_password_common(self, password):
        common_passwords = ['12345678', '11111111', '00000000', 'password', 'password0', 'password1', 'decide', 'decide password', '01234567', 
        '2345678','password123', 'password12', 'cotraseña', 'contraseña123','adminadmin', 'admin123', '1234567890',
        '0987654321', '87654321','lorca123','lorca_password']

        res = False
        for c in common_passwords:

            if (password==c):
                res = True
                break
        
        return res

    def clean_password_too_similar(self, password, username, first_name, last_name):
        if (password.__contains__(username) | password.__contains__(first_name) | password.__contains__(last_name)):
            return True
            
        else:
            return False

    def clean_password_numeric(self, password):
        if (password.isnumeric()):
            return True
        else:
            return False


class GetUserView(APIView):
    def post(self, request):
        key = request.data.get('token', '')
        tk = get_object_or_404(Token, key=key)
        return Response(UserSerializer(tk.user, many=False).data)


class LogoutView(APIView):
    def post(self, request):
        key = request.data.get('token', '')
        try:
            tk = Token.objects.get(key=key)
            tk.delete()
        except ObjectDoesNotExist:
            pass

        return Response({})


class RegisterViewAPI(APIView):
    def post(self, request):
        key = request.data.get('token', '')
        tk = get_object_or_404(Token, key=key)
        if not tk.user.is_superuser:
            return Response({}, status=HTTP_401_UNAUTHORIZED)

        username = request.data.get('username', '')
        pwd = request.data.get('password', '')
        if not username or not pwd:
            return Response({}, status=HTTP_400_BAD_REQUEST)

        try:
            user = User(username=username)
            user.set_password(pwd)
            user.save()
            token, _ = Token.objects.get_or_create(user=user)
        except IntegrityError:
            return Response({}, status=HTTP_400_BAD_REQUEST)
        return Response({'user_pk': user.pk, 'token': token.key}, HTTP_201_CREATED)

class LoginView(CreateView):

    template_name = "authentication/login.html"
    form_class = CustomUserCreationForm
    model = User

    def post(self, request):
        values = request.POST  

        username = values['username']
        password1 = values['password1']
        
        user = authenticate(request, username=username, password=password1)

        url = reverse_lazy('welcome')
        response = redirect(url)

        if user is not None:
            login(request, user)
            userObject = User.objects.get(username=username)
            token, created = Token.objects.get_or_create(user=userObject)
            response.set_cookie(key='token', value=token)
        else:
            incorrect = ["Username and password do not exist"]
            template = loader.get_template("authentication/authentication.html")
            context = {"errors":incorrect}

            return HttpResponse(template.render(context, request))

        return response

    
class RegisterView(CreateView):
    template_name = "authentication/authentication.html"
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    model = User

    def get_form(self, form_class=None):
        form = super(RegisterView, self).get_form()
        form.fields['username'].widget = forms.TextInput(attrs={'class':'form-control mb-2', 'placeholder':'Less than 150 characters'})
        form.fields['password1'].widget = forms.PasswordInput(attrs={'class':'form-control mb-2', 'placeholder':'8 characters or more'}) 
        form.fields['password2'].widget = forms.PasswordInput(attrs={'class':'form-control mb-2', 'placeholder':'Confirm password'}) 
        form.fields['first_name'].widget = forms.TextInput(attrs={'class':'form-control mb-2', 'placeholder':'Alex'}) 
        form.fields['last_name'].widget = forms.TextInput(attrs={'class':'form-control mb-2', 'placeholder':'Smith'}) 
        form.fields['email'].widget = forms.EmailInput(attrs={'class':'form-control mb-2', 'placeholder':'example@decide.com'}) 

        return form

    def get_success_url(self):
        return reverse_lazy("/authentication/login")

    def post(self, request):
        values = request.POST   

        username = values['username']
        password1 = values['password1']
        password2 = values['password2']
        email = values['email']
        first_name = values['first_name']
        last_name = values['last_name']
        form = CustomUserCreationForm()

        errors = []


        if(form.clean_confirmation(password1, password2)):
            errors.append("Passwords must be the same")

        if(form.username_clean_lenght(username)):
            errors.append("This username is larger than 150 characters")
           
        if(form.username_clean_exits(username)):
            errors.append("This username has already taken")

        if(form.username_clean_pattern(username)):
            errors.append("This username not match with the pattern")

        if(form.email_clean(email)):
            errors.append("This email has already taken")
            
        if(form.clean_password_lenght(password1)):
            errors.append("This password must contain at least 8 characters")

        if(form.clean_password_common(password1)):
            errors.append("This password is a common password")

        if(form.clean_password_too_similar(password1, username, first_name, last_name)):
            errors.append("This password is too similar to your personal data")

        if(form.clean_password_numeric(password1)):
            errors.append("This password is numeric")


        if (len(errors)>0):
            template = loader.get_template("authentication/authentication.html")
            context = {"errors":errors}

            return HttpResponse(template.render(context, request))
        else:
            try:
                user = User(username=username)
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.set_password(password1)

                email=EmailMessage("Message from the app Decide", 

                "This is a confirmation message: the user with name {} and email {} has registered in the app Decide recently.".format(user.first_name,user.email), 

                "",[user.email], reply_to=[email])

                email.send()
                user.save()
                token, _ = Token.objects.get_or_create(user=user)

            except IntegrityError:
                return HttpResponse("Integrity Error raised", status=HTTP_400_BAD_REQUEST)
            
            url = reverse_lazy('welcome')
            return redirect(url)


def main(request):
    template = loader.get_template("authentication/welcome.html")
    context = {}
    is_authenticated = False
    votings=[]

    if request.user.is_authenticated == True:
        is_authenticated = True
        context['username'] = request.user.username
        census = Census.objects.filter(voter_id=request.user.id)
        for c in census:
            voting_id = c.voting_id

            voting = Voting.objects.get(id = voting_id)
            
            if voting is not None and voting.start_date is not None and voting.end_date is None:
                votings.append(voting) 

    context['authenticated'] = is_authenticated
    context['votings'] = votings

    return HttpResponse(template.render(context, request))


def logout_view(request):
    url = reverse_lazy('welcome')
    response = redirect(url)
    if request.user.is_authenticated == True:
        logout(request)
        response.delete_cookie('token')
        response.delete_cookie('decide')
    return response
