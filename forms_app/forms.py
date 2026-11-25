import json

from django import forms

from .models import Question, Questionnaire


CHOICE_TYPES = {
    Question.QuestionType.SINGLE_CHOICE,
    Question.QuestionType.MULTIPLE_CHOICE,
    Question.QuestionType.DROPDOWN,
}


class QuestionnaireBuilderForm(forms.ModelForm):
    """Metadata plus a JSON payload managed by the builder JavaScript."""

    questions_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_questions_json'}),
    )

    class Meta:
        model = Questionnaire
        fields = (
            'title',
            'description',
            'language',
            'seconds_per_question',
            'allow_anonymous',
            'show_respondent_username',
            'questions_json',
        )
        widgets = {
            'title': forms.TextInput(attrs={'maxlength': 120, 'placeholder': 'Contoh: Kebiasaan belajar mahasiswa'}),
            'description': forms.Textarea(attrs={'maxlength': 1000, 'rows': 4, 'placeholder': 'Jelaskan tujuan kuesioner ini (opsional)'}),
            'language': forms.Select(),
            'seconds_per_question': forms.NumberInput(attrs={'min': 10, 'max': 20}),
        }
        labels = {
            'title': 'Judul kuesioner',
            'description': 'Deskripsi',
            'language': 'Bahasa kuesioner',
            'seconds_per_question': 'Waktu minimal per pertanyaan (detik)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seconds_per_question'].widget.attrs.update({'min': 10, 'max': 20})

    def clean_questions_json(self):
        raw = self.cleaned_data.get('questions_json') or '[]'
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise forms.ValidationError('Format pertanyaan tidak valid.') from exc

        if not isinstance(payload, list):
            raise forms.ValidationError('Data pertanyaan harus berupa daftar.')
        if len(payload) > 20:
            raise forms.ValidationError('Maksimal 20 pertanyaan per kuesioner.')

        normalized = []
        valid_types = {value for value, _label in Question.QuestionType.choices}
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise forms.ValidationError(f'Pertanyaan #{index} tidak valid.')

            question_type = item.get('question_type')
            if question_type not in valid_types:
                raise forms.ValidationError(f'Tipe pertanyaan #{index} tidak valid.')

            text = str(item.get('text', '')).strip()
            if not text:
                raise forms.ValidationError(f'Teks pertanyaan #{index} wajib diisi.')
            if len(text) > 300:
                raise forms.ValidationError(f'Teks pertanyaan #{index} maksimal 300 karakter.')

            options = item.get('options', [])
            if not isinstance(options, list):
                raise forms.ValidationError(f'Opsi pertanyaan #{index} tidak valid.')
            options = [str(option).strip() for option in options if str(option).strip()]
            if question_type in CHOICE_TYPES:
                if not options:
                    raise forms.ValidationError(f'Pertanyaan pilihan #{index} harus memiliki opsi.')
                if len(options) > 10:
                    raise forms.ValidationError(f'Maksimal 10 opsi pada pertanyaan #{index}.')
                if len(options) != len(set(options)):
                    raise forms.ValidationError(f'Opsi pada pertanyaan #{index} tidak boleh duplikat.')
            else:
                options = []

            try:
                rating_max = int(item.get('rating_max', 5))
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f'Nilai maksimum rating #{index} tidak valid.') from exc
            if question_type == Question.QuestionType.RATING and not 2 <= rating_max <= 100:
                raise forms.ValidationError(f'Skala rating #{index} harus antara 2 dan 100.')
            if question_type != Question.QuestionType.RATING:
                rating_max = 5

            is_required = item.get('is_required', True)
            if isinstance(is_required, str):
                is_required = is_required.lower() not in {'', '0', 'false', 'no', 'off'}
            else:
                is_required = bool(is_required)

            normalized.append({
                'question_type': question_type,
                'text': text,
                'is_required': is_required,
                'options': options,
                'rating_max': rating_max,
            })

        return normalized

    @property
    def questions_payload(self):
        return self.cleaned_data.get('questions_json', [])


class PublishQuestionnaireForm(forms.Form):
    duration_days = forms.TypedChoiceField(
        choices=[(day, f'{day} hari') for day in range(1, 8)],
        coerce=int,
        initial=7,
        widget=forms.Select(attrs={'class': 'select-control'}),
        label='Masa berlaku',
    )
    content_ack = forms.BooleanField(
        required=True,
        label='Saya memastikan kuesioner ini tidak memuat konten terlarang.',
    )
    lock_ack = forms.BooleanField(
        required=True,
        label='Saya memahami kuesioner tidak dapat diubah setelah diterbitkan.',
    )
