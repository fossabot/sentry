import ExternalLink from 'sentry/components/links/externalLink';
import {StepType} from 'sentry/components/onboarding/gettingStartedDoc/step';
import type {
  Docs,
  DocsParams,
  OnboardingConfig,
} from 'sentry/components/onboarding/gettingStartedDoc/types';
import {
  getCrashReportModalConfigDescription,
  getCrashReportModalIntroduction,
  getCrashReportSDKInstallFirstStepRails,
} from 'sentry/components/onboarding/gettingStartedDoc/utils/feedbackOnboarding';
import {getRubyMetricsOnboarding} from 'sentry/components/onboarding/gettingStartedDoc/utils/metricsOnboarding';
import replayOnboardingJsLoader from 'sentry/gettingStartedDocs/javascript/jsLoader/jsLoader';
import {t, tct} from 'sentry/locale';

type Params = DocsParams;

const getInstallSnippet = (
  params: Params
) => `${params.isProfilingSelected ? 'gem "stackprof"\n' : ''}gem "sentry-ruby"
gem "sentry-rails"`;

const getConfigureSnippet = (params: Params) => `
Sentry.init do |config|
  config.dsn = '${params.dsn}'
  config.breadcrumbs_logger = [:active_support_logger, :http_logger]${
    params.isPerformanceSelected
      ? `

  # Set traces_sample_rate to 1.0 to capture 100%
  # of transactions for performance monitoring.
  # We recommend adjusting this value in production.
  config.traces_sample_rate = 1.0
  # or
  config.traces_sampler = lambda do |context|
    true
  end`
      : ''
  }${
    params.isProfilingSelected
      ? `
  # Set profiles_sample_rate to profile 100%
  # of sampled transactions.
  # We recommend adjusting this value in production.
  config.profiles_sample_rate = 1.0`
      : ''
  }
end`;

const getVerifyRailsSnippet = () => `
Sentry.capture_message("test message")`;

const onboarding: OnboardingConfig = {
  introduction: () =>
    t(
      'In Rails, all uncaught exceptions will be automatically reported. We support Rails 5 and newer.'
    ),
  install: (params: Params) => [
    {
      type: StepType.INSTALL,
      description: tct(
        'The Sentry SDK for Rails comes as two gems and is straightforward to install. If you are using Bundler just add this to your [gemfileCode:Gemfile] and run [bundleCode:bundle install]:',
        {
          gemfileCode: <code />,
          bundleCode: <code />,
        }
      ),
      configurations: [
        {
          description: params.isProfilingSelected
            ? tct(
                'Ruby Profiling beta is available since SDK version 5.9.0. We use the [stackprofLink:stackprof gem] to collect profiles for Ruby. Make sure [stackprofCode:stackprof] is loaded before [sentryRubyCode:sentry-ruby].',
                {
                  stackprofLink: (
                    <ExternalLink href="https://github.com/tmm1/stackprof" />
                  ),
                  stackprofCode: <code />,
                  sentryRubyCode: <code />,
                }
              )
            : undefined,
          language: 'ruby',
          code: getInstallSnippet(params),
        },
      ],
    },
  ],
  configure: (params: Params) => [
    {
      type: StepType.CONFIGURE,
      description: tct(
        'Run [generate:bin/rails generate sentry] to create the initializer file [code:config/initializers/sentry.rb] and configure it as follows:',
        {
          code: <code />,
        }
      ),
      configurations: [
        {
          language: 'ruby',
          code: getConfigureSnippet(params),
        },
      ],
    },
    {
      title: t('Caveats'),
      description: tct(
        'Currently, custom exception applications [code:(config.exceptions_app)] are not supported. If you are using a custom exception app, you must manually integrate Sentry yourself.',
        {
          code: <code />,
        }
      ),
    },
  ],
  verify: () => [
    {
      type: StepType.VERIFY,
      description: t(
        "This snippet contains an intentional error and can be used as a test to make sure that everything's working as expected."
      ),
      configurations: [
        {
          code: [
            {
              label: 'ruby',
              value: 'ruby',
              language: 'ruby',
              code: getVerifyRailsSnippet(),
            },
          ],
        },
      ],
    },
  ],
  nextSteps: () => [],
};

const crashReportOnboarding: OnboardingConfig = {
  introduction: () => getCrashReportModalIntroduction(),
  install: (params: Params) => [
    {
      type: StepType.INSTALL,
      description: tct(
        "In Rails, being able to serve dynamic pages in response to errors is required to pass the needed [codeEvent:event_id] to the JavaScript SDK. [link:Read our docs] to learn more. Once you're able to serve dynamic exception pages, you can support user feedback.",
        {
          codeEvent: <code />,
          link: (
            <ExternalLink href="https://docs.sentry.io/platforms/ruby/guides/rails/user-feedback/#integration" />
          ),
        }
      ),
      configurations: [
        getCrashReportSDKInstallFirstStepRails(params),
        {
          description: t(
            'Additionally, you need the template that brings up the dialog:'
          ),
          code: [
            {
              label: 'ERB',
              value: 'erb',
              language: 'erb',
              code: `<% sentry_id = request.env["sentry.error_event_id"] %>
<% if sentry_id.present? %>
<script>
  Sentry.init({ dsn: "${params.dsn}" });
  Sentry.showReportDialog({ eventId: "<%= sentry_id %>" });
</script>
<% end %>`,
            },
          ],
        },
      ],
    },
  ],
  configure: () => [
    {
      type: StepType.CONFIGURE,
      description: getCrashReportModalConfigDescription({
        link: 'https://docs.sentry.io/platforms/ruby/guides/rails/user-feedback/configuration/#crash-report-modal',
      }),
    },
  ],
  verify: () => [],
  nextSteps: () => [],
};

const docs: Docs = {
  onboarding,
  customMetricsOnboarding: getRubyMetricsOnboarding(),
  replayOnboardingJsLoader,
  crashReportOnboarding,
};

export default docs;
