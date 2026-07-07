import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Ignition Lint',
  tagline: 'Static analysis for Ignition Perspective views',
  favicon: 'img/logo.svg',

  future: {
    v4: true,
  },

  url: 'https://bw-design-group.github.io',
  baseUrl: '/ignition-lint/',

  organizationName: 'bw-design-group',
  projectName: 'ignition-lint',
  trailingSlash: false,

  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  plugins: [
    [
      '@signalwire/docusaurus-plugin-llms-txt',
      {
        siteTitle: 'ignition-lint',
        siteDescription: 'Static analysis for Ignition Perspective views',
        depth: 2,
        content: {
          enableLlmsFullTxt: true,
          // The site is served under baseUrl '/ignition-lint/'. With the
          // default relativePaths: true, the plugin writes root-rooted links
          // like '/getting-started/installation.md' that 404 on GitHub Pages.
          // relativePaths: false makes it emit baseUrl-prefixed links
          // ('/ignition-lint/getting-started/installation.md') that resolve.
          relativePaths: false,
          // The search page is not useful content for an LLM index.
          // Patterns match the full route path, which includes the baseUrl
          // (e.g. '/ignition-lint/search'), so use a baseUrl-independent glob.
          excludeRoutes: ['**/search'],
        },
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
          editUrl:
            'https://github.com/bw-design-group/ignition-lint/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themes: [
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: true,
        indexDocs: true,
        indexBlog: false,
        indexPages: false,
        language: ['en'],
        highlightSearchTermsOnTargetPage: true,
      },
    ],
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Ignition Lint',
      logo: {
        alt: 'Ignition Lint logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/bw-design-group/ignition-lint',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {label: 'Introduction', to: '/'},
            {label: 'Getting Started', to: '/getting-started/installation'},
            {label: 'Tutorial', to: '/tutorial'},
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/bw-design-group/ignition-lint',
            },
            {
              label: 'PyPI',
              href: 'https://pypi.org/project/ign-lint/',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} BW Design Group.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'json', 'bash', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
