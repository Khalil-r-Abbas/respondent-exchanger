from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm

from accounts.utils import apakah_email_sekali_pakai

User = get_user_model()


class FormPendaftaran(UserCreationForm):
    """Form pendaftaran akun baru dengan validasi email unik dan blokir email sekali pakai."""

    email = forms.EmailField(
        required=True,
        label='Alamat Email',
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'nama@kampus.ac.id',
                'autocomplete': 'email',
            }
        ),
    )

    class Meta:
        model = User
        fields = ('username', 'email')
        labels = {
            'username': 'Username',
        }
        widgets = {
            'username': forms.TextInput(
                attrs={
                    'placeholder': 'contoh: andi_sutanto',
                    'autocomplete': 'username',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Kata Sandi'
        self.fields['password1'].widget.attrs.update({
            'placeholder': 'Minimal 8 karakter',
            'autocomplete': 'new-password',
        })
        self.fields['password2'].label = 'Konfirmasi Kata Sandi'
        self.fields['password2'].widget.attrs.update({
            'placeholder': 'Ulangi kata sandi',
            'autocomplete': 'new-password',
        })

    def clean_email(self):
        email_bersih = self.cleaned_data.get('email', '').strip().lower()

        # Tolak domain email sekali pakai (disposable email)
        if apakah_email_sekali_pakai(email_bersih):
            raise forms.ValidationError(
                'Email sekali pakai (disposable email) tidak diperbolehkan untuk mendaftar.'
            )

        # Pastikan email belum digunakan oleh akun lain (case-insensitive)
        if User.objects.filter(email__iexact=email_bersih).exists():
            raise forms.ValidationError('Alamat email ini sudah terdaftar.')

        return email_bersih


class FormLogin(forms.Form):
    """Form login menggunakan username atau alamat email."""

    pengenal = forms.CharField(
        label='Username atau Email',
        max_length=254,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Username atau email Anda',
                'autocomplete': 'username',
            }
        ),
    )
    password = forms.CharField(
        label='Kata Sandi',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Masukkan kata sandi',
                'autocomplete': 'current-password',
            }
        ),
    )


class FormLupaSandi(PasswordResetForm):
    """Form permintaan tautan reset kata sandi berbahasa Indonesia."""

    email = forms.EmailField(
        label='Alamat Email Terdaftar',
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'nama@kampus.ac.id',
                'autocomplete': 'email',
            }
        ),
    )


class FormSetelSandiBaru(SetPasswordForm):
    """Form penetapan kata sandi baru setelah membuka tautan reset."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Kata Sandi Baru'
        self.fields['new_password1'].widget.attrs.update({
            'placeholder': 'Minimal 8 karakter',
            'autocomplete': 'new-password',
        })
        self.fields['new_password2'].label = 'Konfirmasi Kata Sandi Baru'
        self.fields['new_password2'].widget.attrs.update({
            'placeholder': 'Ulangi kata sandi baru',
            'autocomplete': 'new-password',
        })
