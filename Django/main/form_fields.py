# https://stackoverflow.com/questions/38006200/allow-svg-files-to-be-uploaded-to-imagefield-via-django-admin
import defusedxml.cElementTree as et
from django.core import validators
from django.core.exceptions import ValidationError
from django.forms import ImageField


def validate_image_file_extension(value):
    return validators.FileExtensionValidator(
        allowed_extensions=validators.get_available_image_extensions() + ['svg']
    )(value)


class ImageAndSvgField(ImageField):
    default_validators = [validate_image_file_extension]

    def to_python(self, data):
        try:
            f = super().to_python(data)
        except ValidationError as e:
            if e.code != 'invalid_image':
                raise

            # Give it a chance - maybe its SVG!
            f = data
            if not self.is_svg(f):
                # Nope it is not.
                raise

            f.content_type = 'image/svg+xml'
            if hasattr(f, "seek") and callable(f.seek):
                f.seek(0)
        return f

    def is_svg(self, f):
        if hasattr(f, "seek") and callable(f.seek):
            f.seek(0)

        try:
            doc = et.parse(f)
            root = doc.getroot()
            return root.tag == '{http://www.w3.org/2000/svg}svg'
        except et.ParseError:
            return False
