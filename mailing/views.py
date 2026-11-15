from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView

from .forms import RecipientForm, MessageForm, MailingForm
from .models import Recipient, Message, Mailing, MailingAttempt
from .services import send_mailing


class OwnerRequiredMixin(UserPassesTestMixin):
    """Разрешает редактирование и удаление только владельцу объекта."""
    def test_func(self):
        obj = self.get_object()
        return obj.owner == self.request.user or self.request.user.is_superuser


class HomeView(TemplateView):
    template_name = 'mailing/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        # Серверное кэширование общей статистики (Задание 10)
        stats = cache.get('global_mailing_stats')
        if not stats:
            for mailing in Mailing.objects.all():
                mailing.update_status()
            stats = {
                'total_mailings': Mailing.objects.count(),
                'active_mailings': Mailing.objects.filter(
                    start_time__lte=now,
                    end_time__gte=now,
                    status=Mailing.STATUS_STARTED,
                ).count(),
                'unique_recipients': Recipient.objects.count(),
            }
            cache.set('global_mailing_stats', stats, 60 * 5)  # Кэш на 5 минут

        context.update(stats)

        # Задание 8. Персональная статистика попыток и отправленных сообщений пользователя
        if self.request.user.is_authenticated:
            user_attempts = MailingAttempt.objects.filter(mailing__owner=self.request.user)
            context['user_success_attempts'] = user_attempts.filter(status=MailingAttempt.STATUS_SUCCESS).count()
            context['user_failed_attempts'] = user_attempts.filter(status=MailingAttempt.STATUS_FAILED).count()
            context['user_sent_messages'] = user_attempts.filter(status=MailingAttempt.STATUS_SUCCESS).count()

        return context


# --- Получатели ---
class RecipientListView(LoginRequiredMixin, ListView):
    model = Recipient
    template_name = 'mailing/recipient_list.html'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.has_perm('mailing.can_disable_mailing'):
            return Recipient.objects.all()
        return Recipient.objects.filter(owner=user)


class RecipientCreateView(LoginRequiredMixin, CreateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:recipient_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        cache.delete('global_mailing_stats')
        return super().form_valid(form)


class RecipientUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:recipient_list')


class RecipientDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Recipient
    template_name = 'mailing/confirm_delete.html'
    success_url = reverse_lazy('mailing:recipient_list')


# --- Сообщения ---
class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'mailing/message_list.html'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.has_perm('mailing.can_disable_mailing'):
            return Message.objects.all()
        return Message.objects.filter(owner=user)


class MessageCreateView(LoginRequiredMixin, CreateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:message_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MessageUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:message_list')


class MessageDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Message
    template_name = 'mailing/confirm_delete.html'
    success_url = reverse_lazy('mailing:message_list')


# --- Рассылки ---
class MailingListView(LoginRequiredMixin, ListView):
    model = Mailing
    template_name = 'mailing/mailing_list.html'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.has_perm('mailing.can_disable_mailing'):
            qs = Mailing.objects.all()
        else:
            qs = Mailing.objects.filter(owner=user)
        for mailing in qs:
            mailing.update_status()
        return qs


@method_decorator(cache_page(60), name='dispatch')  # Клиентское/view кэширование (Задание 10)
class MailingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Mailing
    template_name = 'mailing/mailing_detail.html'

    def test_func(self):
        obj = self.get_object()
        user = self.request.user
        return obj.owner == user or user.is_superuser or user.has_perm('mailing.can_disable_mailing')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.update_status()
        return obj


class MailingCreateView(LoginRequiredMixin, CreateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:mailing_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Показываем пользователю только его сообщения и получателей в выпадающих списках
        form.fields['message'].queryset = Message.objects.filter(owner=self.request.user)
        form.fields['recipients'].queryset = Recipient.objects.filter(owner=self.request.user)
        return form

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        self.object.update_status()
        cache.delete('global_mailing_stats')
        return response


class MailingUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:mailing_list')


class MailingDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Mailing
    template_name = 'mailing/confirm_delete.html'
    success_url = reverse_lazy('mailing:mailing_list')


class MailingSendView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def get_object(self):
        return get_object_or_404(Mailing, pk=self.kwargs['pk'])

    def post(self, request, pk):
        mailing = self.get_object()
        success, msg = send_mailing(mailing)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return redirect('mailing:mailing_detail', pk=pk)


class MailingDisableView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Отключение рассылки менеджером (Задание 9)."""
    permission_required = 'mailing.can_disable_mailing'

    def post(self, request, pk):
        mailing = get_object_or_404(Mailing, pk=pk)
        mailing.status = Mailing.STATUS_COMPLETED
        mailing.end_time = timezone.now()
        mailing.save(update_fields=['status', 'end_time'])
        cache.delete('global_mailing_stats')
        messages.warning(request, f'Рассылка #{mailing.pk} принудительно отключена менеджером.')
        return redirect('mailing:mailing_list')
