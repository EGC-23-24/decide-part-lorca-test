import binascii
from django.db import models
from django.db.models import JSONField

from base import mods
from base.models import Auth, Key
import json


class Question(models.Model):
    desc = models.TextField()
    TYPES = [
            ('C', 'Classic question'),
            ('Y', 'Yes/No question'),
            ('M', 'Multiple choice question'),
            ('T', 'Text question')
            ]
    type = models.CharField(max_length=1, choices=TYPES, default='C')

    def save(self):
        super().save()

    def __str__(self):
        return self.desc


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    number = models.PositiveIntegerField(blank=True, null=True)
    option = models.TextField()

    def save(self):
        if not self.number:
            self.number = self.question.options.count() + 2
        if self.question.type in ['C','M']:
            return super().save()

    def __str__(self):
        if self.question.type in ['C','M']:
            return '{} ({})'.format(self.option, self.number)
        else:
            return 'You cannot create an option for a non-Classic or multiple choice question'

class QuestionOptionYesNo(models.Model):
    question = models.ForeignKey(Question, related_name='yesno_options', on_delete=models.CASCADE)
    number = models.PositiveIntegerField(blank=True, null=True)
    option = models.TextField()

    def save(self):
        if not self.number:
            self.number = self.question.options.count() + 2
        if self.question.type == 'Y':
            return super().save()

    def __str__(self):
        if self.question.type == 'Y':
            return '{} - {} ({}) '.format(self.question,self.option, self.number)
        else:
            return 'You cannot create a Yes/No option for a non-Yes/No question'

class Voting(models.Model):
    name = models.CharField(max_length=200)
    desc = models.TextField(blank=True, null=True)
    question = models.ForeignKey(Question, related_name='voting', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    
    future_stop = models.DateTimeField(blank=True, null=True)

    pub_key = models.OneToOneField(Key, related_name='voting', blank=True, null=True, on_delete=models.SET_NULL)
    auths = models.ManyToManyField(Auth, related_name='votings')

    tally = JSONField(blank=True, null=True)
    postproc = JSONField(blank=True, null=True)

    def create_pubkey(self):
        if self.pub_key or not self.auths.count():
            return

        auth = self.auths.first()
        data = {
            "voting": self.id,
            "auths": [ {"name": a.name, "url": a.url} for a in self.auths.all() ],
        }
        key = mods.post('mixnet', baseurl=auth.url, json=data)
        pk = Key(p=key["p"], g=key["g"], y=key["y"])
        pk.save()
        self.pub_key = pk
        self.save()

    def get_votes(self, token=''):
        # gettings votes from store
        votes = mods.get('store', params={'voting_id': self.id}, HTTP_AUTHORIZATION='Token ' + token)
        # anon votes
        votes_format = []
        vote_list = []
        for vote in votes:
            for info in vote:
                if info == 'a':
                    votes_format.append(vote[info])
                if info == 'b':
                    votes_format.append(vote[info])
            vote_list.append(votes_format)
            votes_format = []
        return vote_list

    def tally_votes(self, token=''):
        '''
        The tally is a shuffle and then a decrypt
        '''

        votes = self.get_votes(token)

        auth = self.auths.first()
        shuffle_url = "/shuffle/{}/".format(self.id)
        decrypt_url = "/decrypt/{}/".format(self.id)
        decrypt_aes_url = "/decrypt_aes/{}/".format(self.id)
        auths = [{"name": a.name, "url": a.url} for a in self.auths.all()]

        # first, we do the shuffle
        data = { "msgs": votes }
        response = mods.post('mixnet', entry_point=shuffle_url, baseurl=auth.url, json=data,
                response=True)
        if response.status_code != 200:
            # TODO: manage error
            pass

        # then, we can decrypt that
        data = {"msgs": response.json()}
        response = mods.post('mixnet', entry_point=decrypt_url, baseurl=auth.url, json=data,
                response=True)

        if response.status_code != 200:
            # TODO: manage error
            pass
        
        def decimal_to_ascii(decimal_string):
            decimal_string = str(decimal_string).replace('[', '').replace(']', '')
            try:
                # Convert the decimal string to a list of ASCII characters with length 4
                while len(decimal_string) % 3 != 0:
                    decimal_string = '0' + decimal_string
                ascii_string = ''
                for i in range(0, len(decimal_string), 3):
                    ascii_char = decimal_string[i:i+3]
                    ascii_string += chr(int(ascii_char))
                return ascii_string
            except ValueError:
                # Handle the case where the input is not a valid decimal string
                return "Invalid decimal string"
        
        if self.question.type == 'T':
            data = {"msgs": response.json()}
            for key, values in data.items():
                data[key] = [decimal_to_ascii(v) for v in values]
            self.tally = data
            self.save()
        else:
            self.tally = response.json()
            self.save()
            
        self.do_postproc()
    
        

    def do_postproc(self):
        tally = self.tally
        options = self.question.options.all()

        opts = []
        for opt in options:
            if isinstance(tally, list):
                votes = tally.count(opt.number)
            else:
                votes = 0
            opts.append({
                'option': opt.option,
                'number': opt.number,
                'votes': votes
            })
        # yes/no postproc
        if self.question.type == 'Y':
            yesno_options = self.question.yesno_options.all()
            for opt in yesno_options:
                if isinstance(tally, list):
                    votes = tally.count(opt.number)
                else:
                    votes = 0
                opts.append({
                    'option': opt.option,
                    'number': opt.number,
                    'votes': votes
                })
            data = { 'type': 'IDENTITY', 'options': opts }
 
        #postproc for text questions
        elif self.question.type == 'T':
            text_votes = []
            for msg, votes in tally.items():
                for vote in votes:
                    text_votes.append({'vote': vote})

            data = {'type': 'TEXT', 'text_votes': text_votes}
        else:
            data = { 'type': 'IDENTITY', 'options': opts }
            
        postp = mods.post('postproc', json=data)

        self.postproc = postp
        self.save()

    def __str__(self):
        return self.name