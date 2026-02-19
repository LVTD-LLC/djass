from allauth.account.forms import LoginForm, SignupForm
from django import forms

from apps.core.models import Project, Profile
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
        "mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 "
        "placeholder:text-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 "
        "dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100 dark:placeholder:text-gray-500"
    )
    SELECT_CLASS = (
        "mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 "
        "focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 "
        "dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100"
    )

    repo_url = forms.URLField(required=False)
    author_url = forms.URLField(required=False)
    use_posthog = forms.ChoiceField(choices=BOOL_CHOICES)
    use_buttondown = forms.ChoiceField(choices=BOOL_CHOICES)
    use_s3 = forms.ChoiceField(choices=BOOL_CHOICES)
    use_stripe = forms.ChoiceField(choices=BOOL_CHOICES)
    use_sentry = forms.ChoiceField(choices=BOOL_CHOICES)
    generate_blog = forms.ChoiceField(choices=BOOL_CHOICES)
    generate_docs = forms.ChoiceField(choices=BOOL_CHOICES)
    use_mjml = forms.ChoiceField(choices=BOOL_CHOICES)
    use_ai = forms.ChoiceField(choices=BOOL_CHOICES)
    use_logfire = forms.ChoiceField(choices=BOOL_CHOICES)
    use_healthchecks = forms.ChoiceField(choices=BOOL_CHOICES)
    use_ci = forms.ChoiceField(choices=BOOL_CHOICES)

    class Meta:
        model = Project
        fields = ["name"]

    project_name = forms.CharField(max_length=255, initial="My Awesome Project")
    project_slug = forms.CharField(max_length=255, required=False)
    project_description = forms.CharField(max_length=255, initial="This project will help you be the best in the world")
    author_name = forms.CharField(max_length=255, initial="Jane Doe")
    author_email = forms.EmailField(initial="janedoe@example.com")
    project_main_color = forms.CharField(max_length=32, initial="green")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = self.SELECT_CLASS
            else:
                widget.attrs["class"] = self.TEXT_INPUT_CLASS

    def clean_project_slug(self):
        value = self.cleaned_data.get("project_slug")
        if value:
            return value.replace("-", "_").replace(" ", "_").lower()
        project_name = self.cleaned_data.get("project_name", "project")
        return project_name.replace("-", "_").replace(" ", "_").lower()

    def get_cookiecutter_payload(self):
        keys = [
            "project_name",
            "project_slug",
            "repo_url",
            "project_description",
            "author_name",
            "author_email",
            "author_url",
            "project_main_color",
            "use_posthog",
            "use_buttondown",
            "use_s3",
            "use_stripe",
            "use_sentry",
            "generate_blog",
            "generate_docs",
            "use_mjml",
            "use_ai",
            "use_logfire",
            "use_healthchecks",
            "use_ci",
        ]
        return {key: self.cleaned_data[key] for key in keys}
