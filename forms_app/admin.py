from django.contrib import admin

from .models import Answer, Question, Questionnaire, Report, Response, SubmissionSession


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(Questionnaire)
class QuestionnaireAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'owner',
        'language',
        'status',
        'allow_anonymous',
        'seconds_per_question',
        'link_code',
        'expires_at',
    )
    list_filter = ('status', 'language', 'allow_anonymous', 'show_respondent_username')
    search_fields = ('title', 'link_code', 'owner__username')
    readonly_fields = ('created_at',)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('questionnaire', 'order', 'question_type', 'text', 'is_required', 'rating_max')
    list_filter = ('question_type', 'is_required')
    search_fields = ('text', 'questionnaire__title')


@admin.register(SubmissionSession)
class SubmissionSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'questionnaire', 'user', 'anonymous_key', 'status', 'started_at', 'last_activity_at')
    list_filter = ('status',)
    search_fields = ('questionnaire__title', 'user__username', 'anonymous_key')


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'questionnaire',
        'respondent',
        'duration_seconds',
        'is_too_fast',
        'is_counted',
        'points_awarded',
        'submitted_at',
    )
    list_filter = ('is_too_fast', 'is_counted')
    search_fields = ('questionnaire__title', 'respondent__username')
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'response', 'question', 'value')
    search_fields = ('question__text',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'questionnaire', 'reporter', 'reason', 'created_at')
    list_filter = ('reason',)
    search_fields = ('questionnaire__title', 'reporter__username', 'note')
