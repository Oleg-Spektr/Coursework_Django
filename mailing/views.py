from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView

from .forms import RecipientForm, MessageForm, MailingForm
from .models import Recipient, Message, Mailing
from .services import send_mailing


class HomeView(TemplateView):
    template_name = 'mailing/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        # Актуализируем статусы рассылок перед подсчётом
        for mailing in Mailing.objects.all():
            mailing.update_status()

        context['total_mailings'] = Mailing.objects.count()
        context['active_mailings'] = Mailing.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            status=Mailing.STATUS_STARTED,
        ).count()
        context['unique_recipients'] = Recipient.objects.count()
        return context


# --- CRUD Получателей ---
class RecipientListView(ListView):
    model = Recipient
    template_name = 'mailing/recipient_list.html'


class RecipientCreateView(CreateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:recipient_list')


class RecipientUpdateView(UpdateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:recipient_list')


class RecipientDeleteView(DeleteView):
    model = Recipient
    template_name = 'mailing/confirm_delete.html'
    success_url = reverse_lazy('mailing:recipient_list')


# --- CRUD Сообщений ---
class MessageListView(ListView):
    model = Message
    template_name = 'mailing/message_list.html'


class MessageCreateView(CreateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:message_list')


class MessageUpdateView(UpdateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:message_list')


class MessageDeleteView(DeleteView):
    model = Message
    template_name = 'mailing/confirm_delete.html'
    success_url = reverse_lazy('mailing:message_list')


# --- CRUD Рассылок ---
class MailingListView(ListView):
    model = Mailing
    template_name = 'mailing/mailing_list.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        for mailing in queryset:
            mailing.update_status()
        return queryset


class MailingDetailView(DetailView):
    model = Mailing
    template_name = 'mailing/mailing_detail.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.update_status()  # Динамический пересчёт при открытии страницы
        return obj


class MailingCreateView(CreateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:mailing_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.update_status()
        return response


class MailingUpdateView(UpdateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailing/form.html'
    success_url = reverse_lazy('mailing:mailing_list')


class MailingDeleteView(DeleteView):
    model = Mailing
    template_name = 'mailing/confirm_delete.html'
    success_url = reverse_lazy('mailing:mailing_list')


class MailingSendView(View):
    """Ручной запуск рассылки из интерфейса."""
    def post(self, request, pk):
        mailing = get_object_or_404(Mailing, pk=pk)
        success, msg = send_mailing(mailing)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return redirect('mailing:mailing_detail', pk=pk)
