from django import template
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from .. import common, settings

register = template.Library()


def anchor(parser, token):
    """
    Parses a tag that's supposed to be in this format '{% anchor field title %}'
    Title may be a "string", _("trans string"), or variable
    Optional - default sort direction to desc '{% anchor field title "desc" %}'
    """
    bits = [b for b in token.split_contents()]
    if len(bits) < 2:
        raise template.TemplateSyntaxError("anchor tag takes at least 1 argument.")

    title_is_var = False
    title_is_translatable = False
    try:
        title = bits[2]
        if title[0] in ('"', "'"):
            if title[0] == title[-1]:
                title = title[1:-1]
            else:
                raise template.TemplateSyntaxError(
                    'anchor tag title must be a "string", _("trans string"), or variable'
                )
        elif title.startswith('_("') or title.startswith("_('"):
            title_is_translatable = True
        else:
            title_is_var = True
    except IndexError:
        title = bits[1].capitalize()

    __import__("ipdb").set_trace()
    default_sort_order = (
        "desc" if len(bits) >= 4 and bits[3].strip("'\"") == "desc" else "asc"
    )

    return SortAnchorNode(
        bits[1].strip(),
        title.strip(),
        title_is_var,
        title_is_translatable,
        default_sort_order,
    )


class SortAnchorNode(template.Node):
    """
    Renders an <a> HTML tag with a link which href attribute
    includes the field on which we sort and the direction.
    and adds an up or down arrow if the field is the one
    currently being sorted on.

    Eg.
        {% anchor name Name %} generates
        <a href="/the/current/path/?sort=name&dir=asc" title="Name">Name</a>

    """

    def __init__(
        self, field, title, title_is_var, title_is_translatable, default_sort_order
    ):
        self.field = field
        self.title = title
        self.title_is_var = title_is_var
        self.title_is_translatable = title_is_translatable
        self.default_sort_order = default_sort_order

    def render(self, context):
        if self.title_is_var:
            display_title = context[self.title]
        elif self.title_is_translatable:
            display_title = _(self.title[3:-2])
        else:
            display_title = self.title

        return common.render_sort_anchor(
            context["request"], self.field, display_title, self.default_sort_order
        )


def autosort(parser, token):
    bits = [b.strip("\"'") for b in token.split_contents()]
    help_msg = (
        "autosort tag synopsis: {%% autosort queryset [as " "context_variable] %%}"
    )
    context_var = None

    # Check if their is some optional parameter (as new_context_var, nulls)
    if 2 > len(bits) > 7:
        raise template.TemplateSyntaxError(help_msg)

    context_var = None
    null_ordering = None

    for index, bit in enumerate(bits):
        if index > 1:
            if bit == "as" and index + 1 < len(bits):
                context_var = bits[index + 1]
                del bits[index : index + 1]
            if bit.startswith("nulls"):
                null_ordering = bit[len("nulls=") :]

    return SortedDataNode(bits[1], null_ordering, context_var=context_var)


class SortedDataNode(template.Node):
    """
    Automatically sort a queryset with {% autosort queryset %}
    """

    def __init__(self, queryset_var, null_ordering, context_var=None):
        self.queryset_var = template.Variable(queryset_var)
        self.context_var = context_var
        self.null_ordering = null_ordering

    def render(self, context):
        if self.context_var is not None:
            key = self.context_var
        else:
            key = self.queryset_var.var

        queryset = self.queryset_var.resolve(context)
        order_by = common.get_order_by_from_request(context["request"])
        null_ordering = common.get_null_ordering(context["request"], self.null_ordering)

        try:
            context[key] = common.sort_queryset(queryset, order_by, null_ordering)
        except ValueError as e:
            raise template.TemplateSyntaxError from e
        except AttributeError:
            if settings.INVALID_FIELD_RAISES_404:
                raise Http404(
                    "Invalid field sorting. If INVALID_FIELD_RAISES_404 were set to "
                    "False, the error would have been ignored."
                )
            context[key] = queryset

        return ""


anchor = register.tag(anchor)
autosort = register.tag(autosort)
