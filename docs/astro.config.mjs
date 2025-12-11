import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import rehypeExternalLinks from 'rehype-external-links';

export default defineConfig({
	markdown: {
		rehypePlugins: [
			[rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]
		],
	},
	site: 'https://opencitations.github.io',
	base: '/piccione',

	integrations: [
		starlight({
			title: 'Piccione',
			logo: {
				src: './public/piccione.png',
				alt: 'Piccione logo',
			},
			favicon: '/favicon.ico',
			description: 'A Python toolkit for uploading and downloading data to external repositories and cloud services.',

			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/opencitations/piccione' },
			],

			sidebar: [
				{ label: 'Getting started', slug: 'getting_started' },
				{
					label: 'Upload',
					items: [
						{ label: 'Figshare', slug: 'upload/figshare' },
						{ label: 'Zenodo', slug: 'upload/zenodo' },
						{ label: 'Internet Archive', slug: 'upload/internet_archive' },
						{ label: 'Triplestore', slug: 'upload/triplestore' },
					],
				},
				{
					label: 'Download',
					items: [
						{ label: 'Figshare', slug: 'download/figshare' },
						{ label: 'SharePoint', slug: 'download/sharepoint' },
					],
				},
			],
		}),
	],
});
