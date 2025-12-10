import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import rehypeExternalLinks from 'rehype-external-links';

export default defineConfig({
	markdown: {
		rehypePlugins: [
			[rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]
		],
	},
	site: 'https://{{GITHUB_USERNAME}}.github.io',
	base: '/{{PACKAGE_NAME}}',

	integrations: [
		starlight({
			title: '{{PACKAGE_TITLE}}',
			description: '{{DESCRIPTION}}',

			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/{{GITHUB_USERNAME}}/{{PACKAGE_NAME}}' },
			],

			sidebar: [
				{
					label: 'Guides',
					items: [
						{ label: 'Getting started', slug: 'getting_started' },
					],
				},
			],
		}),
	],
});
