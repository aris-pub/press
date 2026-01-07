import numpy as np
from bokeh.plotting import figure
from bokeh.layouts import column, row
from bokeh.models import Slider, Div, CustomJS, ColumnDataSource
from bokeh.embed import components
from bokeh.resources import INLINE

# Initial parameters
omega0_init = 2.0
gamma_init = 0.5
x0_init = 1.0
v0_init = 0.0

def solve_damped_oscillator(omega0, gamma, x0, v0, t_max=15, dt=0.01):
    """Solve damped harmonic oscillator using RK4."""
    steps = int(t_max / dt)
    t = np.zeros(steps)
    x = np.zeros(steps)
    v = np.zeros(steps)

    t[0] = 0
    x[0] = x0
    v[0] = v0

    for i in range(1, steps):
        ti = t[i-1]
        xi = x[i-1]
        vi = v[i-1]

        k1v = vi
        k1a = -2*gamma*vi - omega0**2*xi

        k2v = vi + 0.5*dt*k1a
        k2a = -2*gamma*(vi + 0.5*dt*k1a) - omega0**2*(xi + 0.5*dt*k1v)

        k3v = vi + 0.5*dt*k2a
        k3a = -2*gamma*(vi + 0.5*dt*k2a) - omega0**2*(xi + 0.5*dt*k2v)

        k4v = vi + dt*k3a
        k4a = -2*gamma*(vi + dt*k3a) - omega0**2*(xi + dt*k3v)

        t[i] = ti + dt
        x[i] = xi + (dt/6)*(k1v + 2*k2v + 2*k3v + k4v)
        v[i] = vi + (dt/6)*(k1a + 2*k2a + 2*k3a + k4a)

    return t, x, v

# Initial solution
t, x, v = solve_damped_oscillator(omega0_init, gamma_init, x0_init, v0_init)

# Create data sources
source_position = ColumnDataSource(data=dict(x=t, y=x))
source_phase = ColumnDataSource(data=dict(x=x, y=v))
source_start = ColumnDataSource(data=dict(x=[x0_init], y=[v0_init]))
source_end = ColumnDataSource(data=dict(x=[x[-1]], y=[v[-1]]))

# Create plots
position_plot = figure(width=300, height=250, title="Position vs Time",
                       x_axis_label="Time (s)", y_axis_label="Position (m)")
phase_plot = figure(width=300, height=250, title="Phase Space",
                    x_axis_label="Position (m)", y_axis_label="Velocity (m/s)")

# Position plot
position_plot.line('x', 'y', source=source_position, line_width=2, color='#2c3e50', legend_label='Position x(t)')

# Phase plot
phase_plot.line('x', 'y', source=source_phase, line_width=2, color='#3498db', legend_label='Trajectory')
phase_plot.scatter('x', 'y', source=source_start, size=10, color='#27ae60', legend_label='Start', marker='circle')
phase_plot.scatter('x', 'y', source=source_end, size=10, color='#e74c3c', legend_label='End', marker='square')

# Regime indicator
ratio = gamma_init / omega0_init
if abs(ratio - 1.0) < 0.05:
    regime_text = 'Critically Damped (γ ≈ ω₀)'
    regime_color = '#f57c00'
elif gamma_init < omega0_init:
    regime_text = f'Underdamped (γ < ω₀, ζ = {ratio:.2f})'
    regime_color = '#1976d2'
else:
    regime_text = f'Overdamped (γ > ω₀, ζ = {ratio:.2f})'
    regime_color = '#c2185b'

regime_div = Div(text=f"""
<div style="padding: 12px 20px; border-radius: 6px; font-weight: bold; text-align: center; margin-bottom: 20px; font-size: 16px; background-color: #e3f2fd; color: {regime_color}; border: 2px solid {regime_color};">
    Regime: {regime_text}
</div>
""", sizing_mode='stretch_width', height=60)

# Sliders
omega0_slider = Slider(start=0.5, end=5, value=omega0_init, step=0.1, title="Natural Frequency ω₀ (rad/s)")
gamma_slider = Slider(start=0, end=5, value=gamma_init, step=0.1, title="Damping Coefficient γ (s⁻¹)")
x0_slider = Slider(start=-2, end=2, value=x0_init, step=0.1, title="Initial Displacement x₀ (m)")
v0_slider = Slider(start=-3, end=3, value=v0_init, step=0.1, title="Initial Velocity v₀ (m/s)")

# JavaScript callback
callback = CustomJS(args=dict(
    source_position=source_position,
    source_phase=source_phase,
    source_start=source_start,
    source_end=source_end,
    regime_div=regime_div,
    omega0_slider=omega0_slider,
    gamma_slider=gamma_slider,
    x0_slider=x0_slider,
    v0_slider=v0_slider
), code="""
    const omega0 = omega0_slider.value;
    const gamma = gamma_slider.value;
    const x0 = x0_slider.value;
    const v0 = v0_slider.value;

    const t_max = 15;
    const dt = 0.01;
    const steps = Math.floor(t_max / dt);

    const t = new Array(steps);
    const x = new Array(steps);
    const v = new Array(steps);

    t[0] = 0;
    x[0] = x0;
    v[0] = v0;

    for (let i = 1; i < steps; i++) {
        const ti = t[i-1];
        const xi = x[i-1];
        const vi = v[i-1];

        const k1v = vi;
        const k1a = -2*gamma*vi - omega0*omega0*xi;

        const k2v = vi + 0.5*dt*k1a;
        const k2a = -2*gamma*(vi + 0.5*dt*k1a) - omega0*omega0*(xi + 0.5*dt*k1v);

        const k3v = vi + 0.5*dt*k2a;
        const k3a = -2*gamma*(vi + 0.5*dt*k2a) - omega0*omega0*(xi + 0.5*dt*k2v);

        const k4v = vi + dt*k3a;
        const k4a = -2*gamma*(vi + dt*k3a) - omega0*omega0*(xi + dt*k3v);

        t[i] = ti + dt;
        x[i] = xi + (dt/6)*(k1v + 2*k2v + 2*k3v + k4v);
        v[i] = vi + (dt/6)*(k1a + 2*k2a + 2*k3a + k4a);
    }

    source_position.data = {x: t, y: x};
    source_phase.data = {x: x, y: v};
    source_start.data = {x: [x0], y: [v0]};
    source_end.data = {x: [x[x.length-1]], y: [v[v.length-1]]};

    const ratio = gamma / omega0;
    let regime_text, regime_color;

    if (Math.abs(ratio - 1.0) < 0.05) {
        regime_text = 'Critically Damped (γ ≈ ω₀)';
        regime_color = '#f57c00';
    } else if (gamma < omega0) {
        regime_text = `Underdamped (γ < ω₀, ζ = ${ratio.toFixed(2)})`;
        regime_color = '#1976d2';
    } else {
        regime_text = `Overdamped (γ > ω₀, ζ = ${ratio.toFixed(2)})`;
        regime_color = '#c2185b';
    }

    regime_div.text = `
<div style="padding: 12px 20px; border-radius: 6px; font-weight: bold; text-align: center; margin-bottom: 20px; font-size: 16px; background-color: #e3f2fd; color: ${regime_color}; border: 2px solid ${regime_color};">
    Regime: ${regime_text}
</div>
`;
""")

omega0_slider.js_on_change('value', callback)
gamma_slider.js_on_change('value', callback)
x0_slider.js_on_change('value', callback)
v0_slider.js_on_change('value', callback)

# Layout
sliders_col = column(omega0_slider, gamma_slider, x0_slider, v0_slider)
controls_row = row(sliders_col, regime_div)
plots_row = row(position_plot, phase_plot)
layout = column(controls_row, plots_row)

# Generate components (script and div)
script, div = components(layout)

# Write to HTML file with INLINE resources
with open('/Users/leo.torres/aris/press/seed_papers/damped_oscillator_widget.html', 'w') as f:
    # Include inline Bokeh resources
    f.write(INLINE.render_js())
    f.write('\n')
    f.write(INLINE.render_css())
    f.write('\n')
    # Add centering styles
    f.write('<style>.bk-root > .bk-Column > .bk-Row { display: flex !important; justify-content: center !important; }</style>\n')
    # Include the div
    f.write(div)
    f.write('\n')
    # Include the script without modifications since Bokeh is now embedded
    f.write(script)

print("Damped oscillator widget generated successfully")
