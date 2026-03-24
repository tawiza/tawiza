
import type { Config } from "tailwindcss"

const config = {
  darkMode: ["class"],
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    // Or if using `src` directory:
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  prefix: "",
  theme: {
  	container: {
  		center: true,
  		padding: '2rem',
  		screens: {
  			sm: '576px',
  			'sm-max': {
  				max: '576px'
  			},
  			md: '768px',
  			'md-max': {
  				max: '768px'
  			},
  			lg: '992px',
  			'lg-max': {
  				max: '992px'
  			},
  			xl: '1200px',
  			'xl-max': {
  				max: '1200px'
  			},
  			'2xl': '1320px',
  			'2xl-max': {
  				max: '1320px'
  			},
  			'3xl': '1600px',
  			'3xl-max': {
  				max: '1600px'
  			},
  			'4xl': '1850px',
  			'4xl-max': {
  				max: '1850px'
  			}
  		}
  	},
  	extend: {
  		fontFamily: {
  			jakarta: [
  				'Plus Jakarta Sans',
  				'Inter',
  				'system-ui',
  				'sans-serif'
  			],
  			mono: [
  				'JetBrains Mono',
  				'monospace'
  			]
  		},
  		height: {
  			'300px': '300px',
  			'500px': '500px',
  			sidebar: 'calc(100vh - 32px)'
  		},
  		colors: {
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))',
  				border: 'hsl(var(--border))'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar-background))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			},
  			// Semantic status colors
  			success: 'var(--success)',
  			warning: 'var(--warning)',
  			error: 'var(--error)',
  			info: 'var(--info)',
  			// Depth scale for surfaces
  			surface: {
  				1: 'hsl(var(--card))',
  				2: 'hsl(var(--muted))',
  				3: 'hsl(var(--muted) / 0.5)',
  			}
  		},
  		boxShadow: {
  			'card': 'var(--card-shadow)',
  			'card-hover': 'var(--card-shadow), 0 4px 12px rgba(0, 0, 0, 0.08)',
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		},
  		transitionTimingFunction: {
  			'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
  		}
  	}
  },
  plugins: [require('tailwindcss-animate')],
} satisfies Config

export default config
