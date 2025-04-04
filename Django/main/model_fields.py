# https://stackoverflow.com/questions/38006200/allow-svg-files-to-be-uploaded-to-imagefield-via-django-admin
from django.db.models.fields.files import ImageField

from . import form_fields


class ImageAndSvgField(ImageField):
    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": form_fields.ImageAndSvgField,
                **kwargs,
            }
        )
