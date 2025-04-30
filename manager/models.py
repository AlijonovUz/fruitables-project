import random
import string

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils.translation import get_language
from django.utils import timezone


class MyUser(AbstractUser):
    phone = models.CharField(max_length=13, null=True, blank=True, verbose_name=_('Telefon raqam'))
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name=_('Profil surati'))

    class Meta:
        verbose_name = _('Foydalanuvchi')
        verbose_name_plural = _('Foydalanuvchilar')


class Departament(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name=_('Nomi'))
    slug = models.SlugField(max_length=150, unique=True, verbose_name=_('Identifikatori'))

    def __str__(self):
        return self.name

    def get_slug(self):
        current_language = get_language()
        if current_language == 'uz':
            return self.slug_uz
        elif current_language == 'en':
            return self.slug_en
        return self.slug

    class Meta:
        verbose_name = _("Bo'lim")
        verbose_name_plural = _("Bo'limlar")


class Category(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name=_('Nomi'))
    slug = models.SlugField(max_length=150, unique=True, verbose_name=_('Identifikatori'))
    departament = models.ForeignKey(
        Departament,
        on_delete=models.CASCADE,
        related_name='category',
        verbose_name=_("Bo'limi")
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Kategoriya')
        verbose_name_plural = _('Kategoriyalar')


WEIGHT_TYPES = {
    'kg': _("Kilogram"),
    'g': _("Gram"),
    'mg': _("Milligram"),
    'l': _("Litr"),
    'ml': _("Millilitr")
}

CURRENCY_TYPES = {
    'UZS': _("UZS"),
}


class Product(models.Model):
    name = models.CharField(max_length=250, verbose_name=_('Nomi'))
    slug = models.SlugField(max_length=250, unique=True, verbose_name=_('Identifikatori'))
    description = models.TextField(default=_("Ma'lumot qo'shilmadi."), verbose_name=_('Tavsifi'))
    currency = models.CharField(max_length=3, choices=CURRENCY_TYPES.items(), verbose_name=_('Valyuta'))
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Narxi'),
        validators=[MinValueValidator(0)]
    )
    discount = models.IntegerField(
        default=0,
        verbose_name=_('Chegirma foizi'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Agar mahsulotingizga chegirma qo‘ymoqchi bo‘lsangiz, chegirma foizini (masalan, 50) kiriting. Agar chegirma bermoqchi bo‘lmasangiz, bu maydonga tegmang.')
    )
    quantity = models.IntegerField(default=0, verbose_name=_('Miqdori'), validators=[MinValueValidator(0)])
    quality = models.CharField(max_length=10, verbose_name=_('Sifati'))
    weight = models.CharField(max_length=2, choices=WEIGHT_TYPES.items(), verbose_name=_("O'lchov birligi"))
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', null=True)

    def __str__(self):
        return self.name

    def get_discount_price(self):
        if self.discount > 0:
            discount_price = self.price - (self.price * self.discount) / 100
            return discount_price
        return None

    class Meta:
        verbose_name = _('Mahsulot')
        verbose_name_plural = _('Mahsulotlar')


class ProductImage(models.Model):
    image = models.ImageField(
        upload_to='products/',
        verbose_name=_('Rasmi (500x350)'),
        help_text=_("Rasmning o‘lchami 500x350 piksel bo‘lishi kerak. Iltimos, to‘g‘ri o‘lchamdagi rasmni yuklang!")
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name=_('Mahsuloti'))

    def __str__(self):
        return self.image.name

    class Meta:
        verbose_name = _('Mahsulot surati')
        verbose_name_plural = _('Mahsulot suratlari')


COUPON_TYPES = [
    ('SALE', _('Sotuv chegirmasi')),
    ('FREESHIP', _('Bepul yetkazish')),
]


def generate_coupon_code(prefix, length=8):
    characters = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(characters, k=length))
    return f"{prefix}-{random_part}"


class Coupons(models.Model):
    code = models.CharField(max_length=150, unique=True, blank=True, verbose_name=_('Kodi'))
    coupon_type = models.CharField(max_length=20, choices=COUPON_TYPES, default='SALE', verbose_name=_('Kupon turi'))
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Narxi'))
    count = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name=_('Soni'))
    used_count = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name=_('Ishlatilgan soni'))
    is_active = models.BooleanField(default=True, verbose_name=_('Faolmi'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Yaratilgan vaqt'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Yangilangan vaqt'))
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Amal qilish muddati'))

    def __str__(self):
        return f"{self.code} - {self.coupon_type} - {self.price} so'm"

    class Meta:
        verbose_name = _('Kupon ')
        verbose_name_plural = _('Kuponlar')

    @property
    def is_available(self):
        now = timezone.now()
        return (
            self.is_active and
            self.count > self.used_count and
            (self.expires_at is None or self.expires_at > now)
        )

    def apply_coupon(self, user):
        if UserCoupon.objects.filter(user=user, coupon=self).exists():
            raise ValidationError(_("Siz bu kupondan allaqachon foydalandingiz."))
        if not self.is_available:
            raise ValidationError(_("Bu kuponning muddati tugagan."))
        if self.used_count >= self.count:
            raise ValidationError(_("Bu kupondan foydalanish soni tugagan."))

        UserCoupon.objects.create(user=user, coupon=self)
        self.used_count += 1
        self.save()

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                code = generate_coupon_code(prefix=self.coupon_type)
                if not Coupons.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)


class UserCoupon(models.Model):
    user = models.ForeignKey(MyUser, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupons, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'coupon')
        verbose_name = _('Foydalanuvchi kuponi')
        verbose_name_plural = _('Foydalanuvchi kuponlari')

    def __str__(self):
        return f"{self.user} - {self.coupon.code}"