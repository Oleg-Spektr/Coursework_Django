import secrets
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import CreateView, ListView

from .forms import UserRegisterForm
from .models import User


class RegisterView(CreateView):
    model = User
    form_class = UserRegisterForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False  # Деактивируем до подтверждения email
        token = secrets.token_hex(16)
        user.token = token
        user.save()

        host = self.request.get_host()
        url = f'http://{host}{reverse("users:email_confirm", args=[token])}'
        send_mail(
            subject='Подтверждение регистрации на MailService',
            message=f'Для подтверждения почты перейдите по ссылке: {url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        messages.info(self.request, 'Ссылка для подтверждения email отправлена (проверьте консоль PyCharm).')
        return super().form_valid(form)


def email_verification(request, token):
    user = get_object_or_404(User, token=token)
    user.is_active = True
    user.token = None
    user.save()
    messages.success(request, 'Email успешно подтверждён! Теперь вы можете войти.')
    return redirect(reverse('users:login'))


class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    permission_required = 'users.can_block_user'


class ToggleUserActiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'users.can_block_user'

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if not user.is_superuser:
            user.is_active = not user.is_active
            user.save(update_fields=['is_active'])
            status_text = 'разблокирован' if user.is_active else 'заблокирован'
            messages.success(request, f'Пользователь {user.email} {status_text}.')
        return redirect('users:user_list')
