# coding: utf-8
import re
import logging

from django import forms
from django.forms import ModelForm
from django.forms.models import BaseInlineFormSet
from django.forms.models import inlineformset_factory
from django.forms.models import save_instance
from django.utils.translation import ugettext_lazy as _
from django.utils.functional import curry
from django.core.files.images import get_image_dimensions
from django.contrib.auth.models import Group
from django.core.exceptions import NON_FIELD_ERRORS, MultipleObjectsReturned

from journalmanager import models
from journalmanager import choices
from scielo_extensions import formfields as fields
from django.conf import settings


logger = logging.getLogger(__name__)
SPECIAL_ISSUE_FORM_FIELD_NUMBER = 'spe'


class UserCollectionContext(ModelForm):
    """
    Inherit from this base class if you have a ``collections`` attribute
    that needs to be contextualized with user collections.
    """

    collections = forms.ModelMultipleChoiceField(models.Collection.objects.none(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more collections')}),
        required=True)

    def __init__(self, *args, **kwargs):
        """
        Collection field queryset is overridden to display only
        collections related to a user.

        ``collections_qset`` should not be passed to the superclass
        ``__init__`` method.
        """
        collections_qset = kwargs.pop('collections_qset', None)
        super(UserCollectionContext, self).__init__(*args, **kwargs)

        if collections_qset is not None:
            self.fields['collections'].queryset = models.Collection.objects.filter(
                pk__in=(collection.collection.pk for collection in collections_qset))


class AheadForm(ModelForm):

    class Meta():
        model = models.Journal
        fields = ('previous_ahead_documents', 'current_ahead_documents')
        widgets = {
           'previous_ahead_documents': forms.TextInput(attrs={'class': 'input-small'}),
           'current_ahead_documents': forms.TextInput(attrs={'class': 'input-small'}),
           }


class JournalForm(ModelForm):
    print_issn = fields.ISSNField(max_length=9, required=False)
    eletronic_issn = fields.ISSNField(max_length=9, required=False)
    languages = forms.ModelMultipleChoiceField(models.Language.objects.all(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more languages')}),
        required=True)
    abstract_keyword_languages = forms.ModelMultipleChoiceField(models.Language.objects.all(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more languages')}),
        required=True)
    sponsor = forms.ModelMultipleChoiceField(models.Sponsor.objects.all(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more sponsors')}),
        required=True)
    subject_categories = forms.ModelMultipleChoiceField(models.SubjectCategory.objects.all(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more categories')}),
        required=False)
    study_areas = forms.ModelMultipleChoiceField(models.StudyArea.objects.all(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more study area')}),
        required=True)
    regex = re.compile(r'^(1|2)\d{3}$')

    def save_all(self, creator):
        journal = self.save(commit=False)

        if self.instance.pk is None:
            journal.creator = creator

        journal.save()
        self.save_m2m()
        return journal

    def clean(self):
        cleaned_data = self.cleaned_data
        print_issn = cleaned_data.get("print_issn")
        eletronic_issn = cleaned_data.get("eletronic_issn")

        if not (print_issn or eletronic_issn):
            msg = u'Eletronic ISSN or Print ISSN must be filled.'
            self._errors['scielo_issn'] = self.error_class([msg])

        return cleaned_data

    def clean_acronym(self):
        return self.cleaned_data["acronym"].lower()

    def clean_init_year(self):

        if self.cleaned_data["init_year"]:
            result = self.regex.match(self.cleaned_data["init_year"])

            if result is None:
                raise forms.ValidationError(u'Invalid Date')

        return self.cleaned_data["init_year"]

    def clean_final_year(self):

        if self.cleaned_data["final_year"]:
            result = self.regex.match(self.cleaned_data["final_year"])

            if result is None:
                raise forms.ValidationError(u'Invalid Date')

        return self.cleaned_data["final_year"]

    def clean_cover(self):

        if self.cleaned_data['cover']:

            if not self.cleaned_data['cover'].name:
                if not self.cleaned_data['cover'].content_type in settings.IMAGE_CONTENT_TYPE:
                    raise forms.ValidationError(u'File type is not supported')

            if self.cleaned_data['cover'].size > settings.IMAGE_SIZE:
                raise forms.ValidationError(u'File size not allowed')

            w, h = get_image_dimensions(self.cleaned_data['cover'])

            if w != settings.IMAGE_DIMENSIONS['width_cover']:
                raise forms.ValidationError("The image is %ipx pixel wide. It's supposed to be %spx" % (w, settings.IMAGE_DIMENSIONS['width_cover']))
            if h != settings.IMAGE_DIMENSIONS['height_cover']:
                raise forms.ValidationError("The image is %ipx pixel high. It's supposed to be %spx" % (h, settings.IMAGE_DIMENSIONS['height_cover']))

        return self.cleaned_data['cover']

    def clean_logo(self):

        if self.cleaned_data['logo']:

            if not self.cleaned_data['logo'].name:
                if not self.cleaned_data['logo'].content_type in settings.IMAGE_CONTENT_TYPE:
                    raise forms.ValidationError(u'File type is not supported')

            if self.cleaned_data['logo'].size > settings.IMAGE_SIZE:
                raise forms.ValidationError(u'File size not allowed')

            w, h = get_image_dimensions(self.cleaned_data['logo'])

            if w != settings.IMAGE_DIMENSIONS['width_logo']:
                raise forms.ValidationError("The image is %ipx pixel wide. It's supposed to be %spx" % (w, settings.IMAGE_DIMENSIONS['width_logo']))
            if h != settings.IMAGE_DIMENSIONS['height_logo']:
                raise forms.ValidationError("The image is %ipx pixel high. It's supposed to be %spx" % (h, settings.IMAGE_DIMENSIONS['height_logo']))

        return self.cleaned_data['logo']

    class Meta:

        model = models.Journal
        exclude = ('collections', )
        #Overriding the default field types or widgets
        widgets = {
           'title': forms.TextInput(attrs={'class': 'span9'}),
           'title_iso': forms.TextInput(attrs={'class': 'span9'}),
           'short_title': forms.TextInput(attrs={'class': 'span9'}),
           'previous_title': forms.Select(attrs={'class': 'span9'}),
           'acronym': forms.TextInput(attrs={'class': 'span2'}),
           'scielo_issn': forms.Select(attrs={'class': 'span3'}),
           'subject_descriptors': forms.Textarea(attrs={'class': 'span9'}),
           'init_year': forms.TextInput(attrs={'class': 'datepicker', 'id': 'datepicker0'}),
           'init_vol': forms.TextInput(attrs={'class': 'span2'}),
           'init_num': forms.TextInput(attrs={'class': 'span2'}),
           'final_year': forms.TextInput(attrs={'class': 'datepicker', 'id': 'datepicker1'}),
           'final_vol': forms.TextInput(attrs={'class': 'span2'}),
           'final_num': forms.TextInput(attrs={'class': 'span2'}),
           'url_main_collection': forms.TextInput(attrs={'class': 'span9'}),
           'url_online_submission': forms.TextInput(attrs={'class': 'span9'}),
           'url_journal': forms.TextInput(attrs={'class': 'span9'}),
           'notes': forms.Textarea(attrs={'class': 'span9'}),
           'editorial_standard': forms.Select(attrs={'class': 'span3'}),
           'copyrighter': forms.TextInput(attrs={'class': 'span8'}),
           'index_coverage': forms.Textarea(attrs={'class': 'span9'}),
           'other_previous_title': forms.TextInput(attrs={'class': 'span9'}),
           'editor_address': forms.TextInput(attrs={'class': 'span9'}),
           'publisher_name': forms.TextInput(attrs={'class': 'span9'}),
        }



class CollectionForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super(CollectionForm, self).__init__(*args, **kwargs)

    class Meta:
        model = models.Collection
        exclude = ('collection', )


class SponsorForm(UserCollectionContext):

    def __init__(self, *args, **kwargs):
        super(SponsorForm, self).__init__(*args, **kwargs)

    class Meta:
        model = models.Sponsor
        exclude = ('acronym', 'country', 'state', 'city', 'address_number', 'address_complement',
            'zip_code', 'phone', 'fax', 'cel')

        widgets = {
            'name': forms.TextInput(attrs={'class': 'span6'}),
            'complement': forms.Textarea(attrs={'class': 'span6'}),
            'address': forms.Textarea(attrs={'class': 'span6'}),
            'email': forms.TextInput(attrs={'class': 'span6'}),
        }


class LoginForm(forms.Form):
        username = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-xlarge focused span4', 'placeholder': _('Username or email')}))
        password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input-xlarge focused span4', 'placeholder': _('Password')}))


class UserForm(ModelForm):
    groups = forms.ModelMultipleChoiceField(Group.objects.all(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more groups')}),
        required=False)

    class Meta:
        model = models.User
        exclude = ('is_staff', 'is_superuser', 'last_login', 'date_joined',
                   'user_permissions', 'email', 'password', 'is_active')

    def save(self, commit=True):
        user = super(UserForm, self).save(commit=False)
        #user.set_password(self.cleaned_data["password"])

        if commit:
            user.save()
            self.save_m2m()
        return user


class MembershipForm(ModelForm):
    status = forms.ChoiceField(widget=forms.Select, choices=choices.JOURNAL_PUBLICATION_STATUS)
    reason = forms.CharField(widget=forms.Textarea)

    class Meta():
        model = models.Membership
        exclude = ('journal', 'collection', 'since', 'created_by')

    def save_all(self, user, journal, collection):
        membership = self.save(commit=False)
        membership.journal = journal
        membership.collection = collection
        membership.created_by = user
        membership.save()

class IssueBaseForm(forms.Form):
    section = forms.ModelMultipleChoiceField(
        models.Section.objects.none(),
        widget=forms.SelectMultiple(attrs={'title': _('Select one or more sections')}),
        required=False)
    volume = forms.CharField(required=False)
    publication_start_month = forms.ChoiceField(choices=choices.MONTHS, required=False)
    publication_end_month = forms.ChoiceField(choices=choices.MONTHS, required=False)
    publication_year = forms.IntegerField()
    is_marked_up = forms.BooleanField(required=False)
    use_license = forms.ModelChoiceField(
        queryset=models.UseLicense.objects.none(), required=False, help_text=models.ISSUE_DEFAULT_LICENSE_HELP_TEXT)
    total_documents = forms.IntegerField()
    ctrl_vocabulary = forms.ChoiceField(
        choices=sorted(choices.CTRL_VOCABULARY, key=lambda vocab: vocab[1]),
        required=False)
    editorial_standard = forms.ChoiceField(choices=sorted(
        choices.STANDARD, key=lambda std: std[1]))
    cover = forms.ImageField(required=False)

    def __init__(self, *args, **kwargs):
        """
        Base class for all Issue kinds of forms.

        :param querysets: (kwarg) a dict relating a field and a queryset.
        :param params: (kwarg) a dict of arbitrary params, relevant to
        subclasses only.
        """
        # discarting optional params, if present.
        params = kwargs.pop('params', None)
        querysets = kwargs.pop('querysets', None)
        self.instance = kwargs.pop('instance', None)

        super(IssueBaseForm, self).__init__(*args, **kwargs)

        if querysets:
            for qset in querysets:
                self.fields[qset].queryset = querysets[qset]

    def save(self, commit=True):
        instance = self.instance or models.Issue()
        if self.is_valid():
            return save_instance(self, instance, commit=commit)
        else:
            return None


class RegularIssueForm(IssueBaseForm):
    number = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        params = kwargs.pop('params', {})

        if 'journal' not in params:
            raise TypeError('RegularIssueForm() takes journal in params keyword argument. e.g: params={"journal":<journal>')
        else:
            self.journal = params['journal']

        super(RegularIssueForm, self).__init__(*args, **kwargs)


    def clean(self):
        volume = self.cleaned_data.get('volume')
        number = self.cleaned_data.get('number')
        publication_year = self.cleaned_data.get('publication_year')

        if not (volume or number):
            raise forms.ValidationError(
                _('You must complete at least one of two fields volume or number.'))

        try:
            issue = models.Issue.objects.get(number=number,
                                             volume=volume,
                                             publication_year=publication_year,
                                             journal=self.journal.pk)
        except models.Issue.DoesNotExist:
            # Perfect! A brand new issue!
            pass
        except MultipleObjectsReturned as e:
            logger.error('''
                Multiple issues returned for the same number, volume and year for one journal.
                Traceback: %s'''.strip() % e.message)
            raise forms.ValidationError({NON_FIELD_ERRORS: _('Issue with this Year and (Volume or Number) already exists for this Journal.')})
        else:
            # Issue already exists (handling updates).
            if self.instance is None or (self.instance.pk != issue.pk):
                raise forms.ValidationError({NON_FIELD_ERRORS:\
                    _('Issue with this Year and (Volume or Number) already exists for this Journal.')})

        return self.cleaned_data


class SupplementIssueForm(IssueBaseForm):
    suppl_type = forms.ChoiceField(choices=choices.ISSUE_SUPPL_TYPE, widget=forms.RadioSelect)
    number = forms.CharField(required=False)
    suppl_text = forms.CharField()

    def __init__(self, *args, **kwargs):
        params = kwargs.pop('params', {})

        if 'journal' not in params:
            raise TypeError('SupplementIssueForm() takes journal in params keyword argument. e.g: params={"journal":<journal>')
        else:
            self.journal = params['journal']

        super(SupplementIssueForm, self).__init__(*args, **kwargs)

    def clean(self):
        volume = self.cleaned_data.get('volume', '')
        number = self.cleaned_data.get('number', '')
        suppl_type = self.cleaned_data.get('suppl_type')
        publication_year = self.cleaned_data.get('publication_year')
        suppl_text = self.cleaned_data.get('suppl_text')

        if suppl_type == 'volume' and (volume == '' or number != ''):
            raise forms.ValidationError(_('You must complete the volume filed. Number field must be empty.'))
        elif suppl_type == 'number' and (number == '' or volume != ''):
            raise forms.ValidationError(_('You must complete the number filed. Volume field must be empty.'))
        else:
            try:
                issue = models.Issue.objects.get(volume=volume,
                                                 number=number,
                                                 publication_year=publication_year,
                                                 suppl_text=suppl_text,
                                                 journal=self.journal)
            except models.Issue.DoesNotExist:
                # Perfect! A brand new issue!
                pass
            except MultipleObjectsReturned as e:
                logger.error('''
                    Multiple issues returned for the same number, volume and year for one journal.
                    Traceback: %s'''.strip() % e.message)
                raise forms.ValidationError({NON_FIELD_ERRORS: _('Issue with this Year and (Volume or Number) already exists for this Journal.')})
            else:
                # Issue already exists (handling updates).
                if self.instance is None or (self.instance.pk != issue.pk):
                    raise forms.ValidationError({NON_FIELD_ERRORS:\
                        _('Issue with this Year and (Volume or Number) already exists for this Journal.')})

        return self.cleaned_data


class SpecialIssueForm(RegularIssueForm):
    number = forms.CharField(required=True, initial=SPECIAL_ISSUE_FORM_FIELD_NUMBER, widget=forms.TextInput(attrs={'readonly':'readonly'}))

    def __init__(self, *args, **kwargs):
        # RegularIssueForm expects 'params' is present in kwargs
        params = kwargs.get('params', {})

        if 'journal' not in params:
            raise TypeError('SpecialIssueForm() takes journal in params keyword argument. e.g: params={"journal":<journal>')
        else:
            self.journal = params['journal']

        super(SpecialIssueForm, self).__init__(*args, **kwargs)


    def clean_number(self):
        # override the number value
        return SPECIAL_ISSUE_FORM_FIELD_NUMBER


###########################################
# Section
###########################################

class SectionTitleForm(ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'class': 'checked_trans'}))

    class Meta:
        model = models.SectionTitle
        fields = ('title', 'language',)


class SectionForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super(SectionForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        self.fields['legacy_code'].widget.attrs['readonly'] = True

    def clean_code(self):
        return self.instance.legacy_code

    def save_all(self, journal):
        section = self.save(commit=False)
        section.journal = journal
        section.save()

        return section

    class Meta:
        model = models.Section
        exclude = ('journal', 'code')


def get_all_section_forms(post_dict, journal, section):
    """
    Get all forms/formsets used by the Section form.

    :Parameters:
      - `post_dict`: The POST querydict, even if it is empty
      - `journal`: The journal instance the section is part of
      - `section`: The section instance bound to the form. Must be
        a new instance when creating an empty form
    """
    args = []
    kwargs = {}

    if section:
        kwargs['instance'] = section

    if post_dict:
        args.append(post_dict)

    section_title_formset = inlineformset_factory(models.Section,
        models.SectionTitle, form=SectionTitleForm, extra=1,
        can_delete=True, formset=FirstFieldRequiredFormSet)

    d = {
        'section_form': SectionForm(*args, **kwargs),
        'section_title_formset': section_title_formset(prefix='titles',
            *args, **kwargs),
    }

    return d


###########################################
# Press Release
###########################################

class RegularPressReleaseForm(ModelForm):

    def __init__(self, *args, **kwargs):
        """
        ``journal`` should not be passed to the superclass
        ``__init__`` method.
        """
        self.journal = kwargs.pop('journal', None)
        super(RegularPressReleaseForm, self).__init__(*args, **kwargs)

        if not self.journal:
            raise TypeError('missing journal argument')

        self.fields['issue'].queryset = models.Issue.objects.available().filter(
            journal__pk=self.journal.pk)

    class Meta:
        model = models.RegularPressRelease


class AheadPressReleaseForm(ModelForm):

    class Meta:
        model = models.AheadPressRelease
        exclude = ('journal',)


class PressReleaseTranslationForm(ModelForm):

    def __init__(self, *args, **kwargs):
        """
        ``journal`` should not be passed to the superclass
        ``__init__`` method.
        """
        self.journal = kwargs.pop('journal', None)
        super(PressReleaseTranslationForm, self).__init__(*args, **kwargs)

        if not self.journal:
            raise TypeError('missing journal argument')

        self.fields['language'].queryset = models.Language.objects.filter(
                journal__pk=self.journal.pk)

    class Meta:
        model = models.PressReleaseTranslation


class PressReleaseArticleForm(ModelForm):

    class Meta:
        model = models.PressReleaseArticle


class AheadPressReleaseArticleForm(ModelForm):
    article_pid = forms.CharField(required=True)

    class Meta:
        model = models.PressReleaseArticle

    def clean_article_pid(self):
        if not self.cleaned_data['article_pid']:
            raise forms.ValidationError('Field is required')

        return self.cleaned_data['article_pid']


def get_all_pressrelease_forms(post_dict, journal, pressrelease):
    """
    Get all forms/formsets used by the PressRelease form.

    :Parameters:
      - ``post_dict``: The POST querydict, even if it is empty
      - ``journal``: The journal instance the press-release is part of
      - ``pressrelease``: The instance bound to the form. Must be
        a new instance when creating an empty form
    """
    args = []
    kwargs = {}

    if pressrelease:
        kwargs['instance'] = pressrelease

    if post_dict:
        args.append(post_dict)

    translations_formset = inlineformset_factory(
        models.PressRelease,
        models.PressReleaseTranslation,
        form=PressReleaseTranslationForm,
        extra=1,
        can_delete=True,
        formset=FirstFieldRequiredFormSet)

    translations_formset.form = staticmethod(
        curry(PressReleaseTranslationForm, journal=journal))

    article_formset = inlineformset_factory(
        models.PressRelease,
        models.PressReleaseArticle,
        form=PressReleaseArticleForm,
        extra=1,
        can_delete=True)

    d = {
        'pressrelease_form': RegularPressReleaseForm(journal=journal,
                                                    *args,
                                                    **kwargs),
        'translation_formset': translations_formset(prefix='translation',
                                                    *args,
                                                    **kwargs),
        'article_formset': article_formset(prefix='article',
                                           *args,
                                           **kwargs),
    }

    return d


def get_all_ahead_pressrelease_forms(post_dict, journal, pressrelease):
    """
    Get all forms/formsets used by the AheadPressRelease form.

    :Parameters:
      - ``post_dict``: The POST querydict, even if it is empty
      - ``journal``: The journal instance the press-release is part of
      - ``pressrelease``: The instance bound to the form. Must be
        a new instance when creating an empty form
    """
    args = []
    kwargs = {}

    if pressrelease:
        kwargs['instance'] = pressrelease

    if post_dict:
        args.append(post_dict)

    translations_formset = inlineformset_factory(
        models.PressRelease,
        models.PressReleaseTranslation,
        form=PressReleaseTranslationForm,
        extra=1,
        can_delete=True,
        formset=FirstFieldRequiredFormSet)

    translations_formset.form = staticmethod(
        curry(PressReleaseTranslationForm, journal=journal))

    article_formset = inlineformset_factory(
        models.PressRelease,
        models.PressReleaseArticle,
        form=AheadPressReleaseArticleForm,
        extra=1,
        can_delete=True,
        formset=FirstFieldRequiredFormSet)

    d = {
        'pressrelease_form': AheadPressReleaseForm(*args,
                                                   **kwargs),
        'translation_formset': translations_formset(prefix='translation',
                                                    *args,
                                                    **kwargs),
        'article_formset': article_formset(prefix='article',
                                           *args,
                                           **kwargs),
    }

    return d


class UserCollectionsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        """
        Collection field queryset is overridden to display only
        collections managed by the given user.

        ``user`` should not be passed to the superclass
        ``__init__`` method.
        """
        self._user = kwargs.pop('user', None)
        super(UserCollectionsForm, self).__init__(*args, **kwargs)
        if self._user:
            self.fields['collection'].queryset = models.Collection.objects.get_managed_by_user(self._user)

    class Meta:
        model = models.UserCollections
        exclude = ('is_default', )
        widgets = {
            'collection': forms.Select(attrs={'class': 'span8'}),
        }


class JournalMissionForm(ModelForm):
    class Meta:
        model = models.JournalMission
        widgets = {
            'description': forms.Textarea(attrs={'class': 'span6', 'rows': '3'}),
        }


class JournalTitleForm(ModelForm):
    class Meta:
        model = models.JournalTitle
        widgets = {
            'title': forms.TextInput(attrs={'class': 'span6'}),
        }


class IssueTitleForm(ModelForm):
    class Meta:
        model = models.IssueTitle
        widgets = {
            'title': forms.TextInput(attrs={'class': 'span12'}),
        }


# ## Formsets ##
class FirstFieldRequiredFormSet(BaseInlineFormSet):
    """
    Formset class that makes the first item required in edit and create form.

    Usage: ABCFormSet = inlineformset_factory(models.Wrappee, models.Wrapped,
        extra=1, formset=FirstFieldRequiredFormSet)
    """

    def clean(self):
        super(FirstFieldRequiredFormSet, self).clean()
        count = 0
        for form in self.forms:
            try:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    count += 1
                    break
            except AttributeError:
                pass
        if count < 1:
            raise forms.ValidationError(_('Please fill in at least one form'))
