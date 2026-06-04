from allauth.account.forms import LoginForm, SignupForm
from django import forms
from django.utils.text import slugify

from apps.core.generator_options import (
    COOKIECUTTER_FIELD_DEFAULTS,
    MODULE_FLAG_KEYS,
    get_generator_option_groups,
    get_option_description,
    get_option_label,
)
from apps.core.models import Profile, Project
from apps.core.utils import DivErrorList


class CustomSignUpForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_class = DivErrorList


class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_class = DivErrorList


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()

    class Meta:
        model = Profile
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            profile.save()
        return profile


class ProjectCreateForm(forms.ModelForm):
    BOOL_CHOICES = (("y", "Yes"), ("n", "No"))
    TEXT_INPUT_CLASS = (
        "mt-1 block w-full rounded-[4px] border border-[var(--dj-border)] "
        "bg-[var(--dj-panel-solid)] px-3 py-2 text-sm text-[var(--dj-heading)] "
        "placeholder:text-[var(--dj-soft)] focus:border-[var(--dj-accent)] "
        "focus:outline-none focus:ring-2 "
        "focus:ring-[color-mix(in_srgb,var(--dj-accent)_28%,transparent)]"
    )
    SELECT_CLASS = (
        "mt-1 block w-full rounded-[4px] border border-[var(--dj-border)] "
        "bg-[var(--dj-panel-solid)] px-3 py-2 text-sm text-[var(--dj-heading)] "
        "focus:border-[var(--dj-accent)] focus:outline-none focus:ring-2 "
        "focus:ring-[color-mix(in_srgb,var(--dj-accent)_28%,transparent)]"
    )

    repo_url = forms.URLField(required=False)
    author_url = forms.URLField(required=False)

    class Meta:
        model = Project
        fields = []

    project_name = forms.CharField(
        max_length=255,
        initial=COOKIECUTTER_FIELD_DEFAULTS["project_name"],
        required=True,
    )
    project_slug = forms.CharField(max_length=255, required=True)
    caprover_app_name = forms.CharField(max_length=255, required=False)
    project_description = forms.CharField(
        max_length=255,
        initial=COOKIECUTTER_FIELD_DEFAULTS["project_description"],
        required=False,
    )
    author_name = forms.CharField(
        max_length=255,
        initial=COOKIECUTTER_FIELD_DEFAULTS["author_name"],
        required=False,
    )
    author_email = forms.EmailField(required=False)
    project_main_color = forms.CharField(
        max_length=32,
        initial=COOKIECUTTER_FIELD_DEFAULTS["project_main_color"],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["repo_url"].initial = COOKIECUTTER_FIELD_DEFAULTS["repo_url"]
        self.fields["author_url"].initial = COOKIECUTTER_FIELD_DEFAULTS["author_url"]
        for field_name in MODULE_FLAG_KEYS:
            self.fields[field_name] = forms.ChoiceField(
                choices=self.BOOL_CHOICES,
                initial=COOKIECUTTER_FIELD_DEFAULTS[field_name],
                label=get_option_label(field_name),
                help_text=get_option_description(field_name),
                required=False,
            )

        if self.user and self.user.email:
            self.fields["author_email"].initial = self.user.email

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = self.SELECT_CLASS
            else:
                widget.attrs["class"] = self.TEXT_INPUT_CLASS

    @property
    def generator_option_fields(self):
        return [self[field_name] for field_name in MODULE_FLAG_KEYS]

    @property
    def generator_option_groups(self):
        return [
            {
                "key": group["key"],
                "label": group["label"],
                "fields": [self[option["key"]] for option in group["options"]],
            }
            for group in get_generator_option_groups()
        ]

    def clean_project_slug(self):
        value = self.cleaned_data.get("project_slug", "").strip()
        if not value:
            raise forms.ValidationError("Project slug is required.")

        normalized = slugify(value).replace("-", "_")
        if not normalized:
            raise forms.ValidationError("Project slug must contain letters or numbers.")
        return normalized

    def clean_caprover_app_name(self):
        value = (self.cleaned_data.get("caprover_app_name") or "").strip()
        default_value = COOKIECUTTER_FIELD_DEFAULTS["caprover_app_name"]
        if not value or value == default_value:
            return default_value

        normalized = slugify(value)
        if not normalized:
            raise forms.ValidationError("CapRover app name must contain letters or numbers.")
        return normalized

    def clean_author_email(self):
        value = (self.cleaned_data.get("author_email") or "").strip()
        if value:
            return value
        if self.user and self.user.email:
            return self.user.email
        return ""

    def clean_project_main_color(self):
        value = (self.cleaned_data.get("project_main_color") or "").strip()
        return value or "green"

    def get_cookiecutter_payload(self):
        payload = {}
        for key, default_value in COOKIECUTTER_FIELD_DEFAULTS.items():
            value = self.cleaned_data.get(key)
            if key in MODULE_FLAG_KEYS and value in (None, ""):
                payload[key] = default_value
            else:
                payload[key] = value if value is not None else default_value
        return payload
