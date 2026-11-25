import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import QuestionnaireBuilderForm, PublishQuestionnaireForm
from .models import Question, Questionnaire


MAX_DRAFTS = 6
MAX_ACTIVE_QUESTIONNAIRES = 3


def _question_payload(questionnaire):
    return [
        {
            'question_type': question.question_type,
            'text': question.text,
            'is_required': question.is_required,
            'options': question.options or [],
            'rating_max': question.rating_max,
        }
        for question in questionnaire.questions.all()
    ]


def _save_questions(questionnaire, payload):
    questionnaire.questions.all().delete()
    Question.objects.bulk_create([
        Question(
            questionnaire=questionnaire,
            order=order,
            question_type=item['question_type'],
            text=item['text'],
            is_required=item['is_required'],
            options=item['options'],
            rating_max=item['rating_max'],
        )
        for order, item in enumerate(payload, start=1)
    ])


def _owned_questionnaire(request, pk):
    return get_object_or_404(
        Questionnaire.objects.prefetch_related('questions'),
        pk=pk,
        owner=request.user,
    )


@login_required
def questionnaire_list(request):
    questionnaires = list(
        Questionnaire.objects.filter(owner=request.user)
        .annotate(response_count=Count('responses'))
        .prefetch_related('questions')
    )
    drafts = [item for item in questionnaires if item.status == Questionnaire.Status.DRAFT]
    published = [
        item for item in questionnaires
        if item.status == Questionnaire.Status.PUBLISHED and not item.is_expired
    ]
    ended = [
        item for item in questionnaires
        if item.status != Questionnaire.Status.DRAFT and (item.is_expired or item.status != Questionnaire.Status.PUBLISHED)
    ]
    return render(request, 'forms_app/questionnaire_list.html', {
        'drafts': drafts,
        'published': published,
        'ended': ended,
        'draft_limit': MAX_DRAFTS,
        'active_limit': MAX_ACTIVE_QUESTIONNAIRES,
    })


@login_required
def questionnaire_builder(request, pk=None):
    questionnaire = _owned_questionnaire(request, pk) if pk else None
    if questionnaire and questionnaire.status != Questionnaire.Status.DRAFT:
        messages.error(request, 'Kuesioner yang sudah terbit tidak dapat diubah.')
        return redirect('forms_app:questionnaire_preview', pk=questionnaire.pk)

    if questionnaire is None and request.method == 'GET':
        if Questionnaire.objects.filter(owner=request.user, status=Questionnaire.Status.DRAFT).count() >= MAX_DRAFTS:
            messages.error(request, f'Batas draf tercapai. Maksimal {MAX_DRAFTS} draf per pengguna.')
            return redirect('forms_app:questionnaire_list')

    if request.method == 'POST':
        if questionnaire is None and Questionnaire.objects.filter(
            owner=request.user,
            status=Questionnaire.Status.DRAFT,
        ).count() >= MAX_DRAFTS:
            messages.error(request, f'Batas draf tercapai. Maksimal {MAX_DRAFTS} draf per pengguna.')
            return redirect('forms_app:questionnaire_list')

        form = QuestionnaireBuilderForm(request.POST, instance=questionnaire)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save(commit=False)
                if questionnaire is None:
                    saved.owner = request.user
                saved.status = Questionnaire.Status.DRAFT
                saved.save()
                _save_questions(saved, form.questions_payload)
            messages.success(request, 'Draf kuesioner berhasil disimpan.')
            if request.POST.get('save_and_preview'):
                return redirect('forms_app:questionnaire_preview', pk=saved.pk)
            return redirect('forms_app:questionnaire_edit', pk=saved.pk)
    else:
        initial = {}
        if questionnaire:
            initial['questions_json'] = json.dumps(_question_payload(questionnaire), ensure_ascii=False)
        else:
            initial['questions_json'] = '[]'
        form = QuestionnaireBuilderForm(instance=questionnaire, initial=initial)

    return render(request, 'forms_app/questionnaire_builder.html', {
        'form': form,
        'questionnaire': questionnaire,
        'initial_questions_json': form['questions_json'].value() or '[]',
        'max_questions': 20,
    })


@login_required
def questionnaire_preview(request, pk):
    questionnaire = _owned_questionnaire(request, pk)
    return render(request, 'forms_app/questionnaire_preview.html', {
        'questionnaire': questionnaire,
        'preview': True,
        'minimum_seconds': questionnaire.questions.count() * questionnaire.seconds_per_question,
    })


@login_required
def questionnaire_publish(request, pk):
    questionnaire = _owned_questionnaire(request, pk)
    if questionnaire.status != Questionnaire.Status.DRAFT:
        messages.error(request, 'Hanya draf yang dapat diterbitkan.')
        return redirect('forms_app:questionnaire_preview', pk=pk)

    form = PublishQuestionnaireForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if not getattr(request.user, 'email_verified', False):
            form.add_error(None, 'Email harus terverifikasi sebelum menerbitkan kuesioner.')
        elif not questionnaire.questions.exists():
            form.add_error(None, 'Tambahkan minimal satu pertanyaan sebelum menerbitkan.')
        elif Questionnaire.objects.filter(
            owner=request.user,
            status=Questionnaire.Status.PUBLISHED,
            expires_at__gt=timezone.now(),
        ).exclude(pk=pk).count() >= MAX_ACTIVE_QUESTIONNAIRES:
            form.add_error(None, f'Batas {MAX_ACTIVE_QUESTIONNAIRES} kuesioner aktif tercapai.')
        else:
            now = timezone.now()
            questionnaire.status = Questionnaire.Status.PUBLISHED
            questionnaire.published_at = now
            questionnaire.expires_at = now + timedelta(days=form.cleaned_data['duration_days'])
            questionnaire.save(update_fields=['status', 'published_at', 'expires_at'])
            messages.success(request, 'Kuesioner berhasil diterbitkan dan sekarang terkunci.')
            return redirect('forms_app:questionnaire_preview', pk=pk)

    return render(request, 'forms_app/questionnaire_publish.html', {
        'questionnaire': questionnaire,
        'form': form,
        'minimum_seconds': questionnaire.questions.count() * questionnaire.seconds_per_question,
    })


@login_required
@require_POST
def questionnaire_duplicate(request, pk):
    original = _owned_questionnaire(request, pk)
    if Questionnaire.objects.filter(owner=request.user, status=Questionnaire.Status.DRAFT).count() >= MAX_DRAFTS:
        messages.error(request, f'Batas draf tercapai. Maksimal {MAX_DRAFTS} draf per pengguna.')
        return redirect('forms_app:questionnaire_list')

    with transaction.atomic():
        duplicate = Questionnaire.objects.create(
            owner=request.user,
            title=f'Salinan: {original.title}'[:120],
            description=original.description,
            language=original.language,
            status=Questionnaire.Status.DRAFT,
            allow_anonymous=original.allow_anonymous,
            show_respondent_username=original.show_respondent_username,
            seconds_per_question=original.seconds_per_question,
        )
        _save_questions(duplicate, _question_payload(original))
    messages.success(request, 'Kuesioner berhasil diduplikasi sebagai draf.')
    return redirect('forms_app:questionnaire_edit', pk=duplicate.pk)


@login_required
@require_POST
def questionnaire_delete(request, pk):
    questionnaire = _owned_questionnaire(request, pk)
    questionnaire.delete()
    messages.success(request, 'Kuesioner dan responsnya berhasil dihapus.')
    return redirect('forms_app:questionnaire_list')


def public_questionnaire(request, link_code):
    questionnaire = get_object_or_404(
        Questionnaire.objects.prefetch_related('questions'),
        link_code=link_code,
    )
    if not questionnaire.is_open:
        return render(request, 'forms_app/questionnaire_closed.html', {'questionnaire': questionnaire})
    return render(request, 'forms_app/questionnaire_preview.html', {
        'questionnaire': questionnaire,
        'preview': False,
        'minimum_seconds': questionnaire.questions.count() * questionnaire.seconds_per_question,
    })
