import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import rehypeExternalLinks from 'rehype-external-links';

export default defineConfig({
	markdown: {
		rehypePlugins: [
			[rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]
		],
	},
	site: 'https://arcangelo7.github.io',
	base: '/piccione',

	integrations: [
		starlight({
			title: 'Piccione',
			logo: {
				src: './public/piccione.png',
				alt: 'Piccione logo',
			},
			description: 'A Python toolkit for uploading and downloading data to external repositories and cloud services.',

			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/arcangelo7/piccione' },
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
