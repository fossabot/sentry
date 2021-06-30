from typing import Any, Sequence

from django import forms
from django.http import HttpResponse
from rest_framework.request import Request

from sentry.models import (
    ExternalActor,
    Identity,
    IdentityProvider,
    Integration,
    NotificationSetting,
    OrganizationMember,
    Team,
)
from sentry.notifications.types import NotificationSettingOptionValues, NotificationSettingTypes
from sentry.shared_integrations.exceptions import ApiError
from sentry.types.integrations import ExternalProviders
from sentry.utils.signing import unsign
from sentry.web.decorators import transaction_start
from sentry.web.frontend.base import BaseView
from sentry.web.helpers import render_to_response

from ..client import SlackClient
from ..utils import logger
from . import build_linking_url as base_build_linking_url
from . import never_cache

ALLOWED_METHODS = ["GET", "POST"]
ALLOWED_ROLES = ["admin", "manager", "owner"]

INSUFFICIENT_ROLE_TITLE = "Insufficient role"
INSUFFICIENT_ROLE_MESSAGE = "You must be an admin or higher to link teams."
ALREADY_LINKED_TITLE = "Already linked"
ALREADY_LINKED_MESSAGE = "The {slug} team has already been linked to a Slack channel."
SUCCESS_LINKED_TITLE = "Team linked"
SUCCESS_LINKED_MESSAGE = (
    "The {slug} team will now receive issue alert notifications in the {channel_name} channel."
)


def build_linking_url(
    integration: Integration, slack_id: str, channel_id: str, channel_name: str, response_url: str
) -> str:
    return base_build_linking_url(
        "sentry-integration-slack-link-team",
        integration_id=integration.id,
        slack_id=slack_id,
        channel_id=channel_id,
        channel_name=channel_name,
        response_url=response_url,
    )


def render_error_page(request: Request, body_text: str) -> HttpResponse:
    return render_to_response(
        "sentry/integrations/slack-link-team-error.html",
        request=request,
        context={"body_text": body_text},
    )


def send_slack_message(
    integration: Integration,
    channel_id: str,
    heading: str,
    text: str,
    request: Request,
) -> HttpResponse:
    client = SlackClient()
    token = integration.metadata.get("user_access_token") or integration.metadata["access_token"]
    payload = {
        "token": token,
        "channel": channel_id,
        "text": text,
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        client.post("/chat.postMessage", headers=headers, data=payload, json=True)
    except ApiError as e:
        message = str(e)
        if message != "Expired url":
            logger.error("slack.link-notify.response-error", extra={"error": message})
    else:
        return render_to_response(
            "sentry/integrations/slack-post-linked-team.html",
            request=request,
            context={
                "heading_text": heading,
                "body_text": text,
                "channel_id": channel_id,
                "team_id": integration.external_id,
            },
        )


class SelectTeamForm(forms.Form):  # type: ignore
    team = forms.ChoiceField(label="Team")

    def __init__(self, teams: Sequence[Team], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.fields["team"].choices = [(team.id, team.slug) for team in teams]
        self.fields["team"].widget.choices = self.fields["team"].choices


class SlackLinkTeamView(BaseView):  # type: ignore
    @transaction_start("SlackLinkTeamView")
    @never_cache
    def handle(self, request: Request, signed_params: str) -> HttpResponse:
        if request.method not in ALLOWED_METHODS:
            return render_error_page(request, body_text="HTTP 405: Method not allowed")

        params = unsign(signed_params)
        integration = Integration.objects.get(id=params["integration_id"])
        organization = integration.organizations.all()[0]
        teams = Team.objects.get_for_user(organization, request.user)
        channel_name = params["channel_name"]
        channel_id = params["channel_id"]
        form = SelectTeamForm(teams, request.POST or None)

        if request.method == "GET":
            return self.respond(
                "sentry/integrations/slack-link-team.html",
                {
                    "form": form,
                    "teams": teams,
                    "channel_name": channel_name,
                    "provider": integration.get_provider(),
                },
            )

        if not form.is_valid():
            return render_error_page(request, body_text="HTTP 400: Bad request")

        team_id = form.cleaned_data["team"]
        try:
            team = Team.objects.get(id=team_id, organization=organization)
        except Team.DoesNotExist:
            return render_error_page(request, body_text="HTTP 404: Team does not exist")

        try:
            idp = IdentityProvider.objects.get(type="slack", external_id=integration.external_id)
        except IdentityProvider.DoesNotExist:
            logger.error(
                "slack.action.invalid-team-id", extra={"slack_id": integration.external_id}
            )
            return render_error_page(request, body_text="HTTP 403: Invalid team ID")

        try:
            identity = Identity.objects.select_related("user").get(
                idp=idp, external_id=params["slack_id"]
            )
        except Identity.DoesNotExist:
            logger.error(
                "slack.action.missing-identity", extra={"slack_id": integration.external_id}
            )
            return render_error_page(request, body_text="HTTP 403: User identity does not exist")

        org_member = OrganizationMember.objects.get(user=identity.user, organization=organization)

        if not (
            org_member.role in ALLOWED_ROLES
            and (organization.flags.allow_joinleave or team in org_member.teams.all())
        ):
            return send_slack_message(
                integration,
                channel_id,
                INSUFFICIENT_ROLE_TITLE,
                INSUFFICIENT_ROLE_MESSAGE,
                request,
            )

        external_team, created = ExternalActor.objects.get_or_create(
            actor_id=team.actor_id,
            organization=organization,
            integration=integration,
            provider=ExternalProviders.SLACK.value,
            defaults=dict(
                external_name=channel_name,
                external_id=channel_id,
            ),
        )

        if not created:
            return send_slack_message(
                integration,
                channel_id,
                ALREADY_LINKED_TITLE,
                ALREADY_LINKED_MESSAGE.format(slug=team.slug),
                request,
            )

        # Turn on notifications for all of a team's projects.
        NotificationSetting.objects.update_settings(
            ExternalProviders.SLACK,
            NotificationSettingTypes.ISSUE_ALERTS,
            NotificationSettingOptionValues.ALWAYS,
            team=team,
        )
        return send_slack_message(
            integration,
            channel_id,
            SUCCESS_LINKED_TITLE,
            SUCCESS_LINKED_MESSAGE.format(slug=team.slug, channel_name=channel_name),
            request,
        )
