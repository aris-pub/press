import numpy as np
from scipy.stats import norm
from bokeh.plotting import figure
from bokeh.layouts import column, row
from bokeh.models import Slider, Div, CustomJS, ColumnDataSource
from bokeh.embed import components
from bokeh.resources import INLINE

# Initial parameters
threshold_init = 0.5
separation_init = 1.5
prevalence_init = 10

# Calculate initial data
mean_healthy = 0
mean_diseased = separation_init
std = 1
prev = prevalence_init / 100

x = np.linspace(-4, 7, 500)
y_healthy = norm.pdf(x, mean_healthy, std)
y_diseased = norm.pdf(x, mean_diseased, std)

# Metrics
sensitivity = 1 - norm.cdf(threshold_init, mean_diseased, std)
specificity = norm.cdf(threshold_init, mean_healthy, std)
ppv = (sensitivity * prev) / (sensitivity * prev + (1 - specificity) * (1 - prev))
npv = (specificity * (1 - prev)) / ((1 - sensitivity) * prev + specificity * (1 - prev))

# ROC curve
thresholds_roc = np.linspace(-3, separation_init + 3, 100)
tpr = 1 - norm.cdf(thresholds_roc, mean_diseased, std)
fpr = 1 - norm.cdf(thresholds_roc, mean_healthy, std)
auc = np.trapezoid(tpr[::-1], fpr[::-1])

# Create data sources
source_healthy = ColumnDataSource(data=dict(x=x, y=y_healthy))
source_diseased = ColumnDataSource(data=dict(x=x, y=y_diseased))
source_threshold = ColumnDataSource(data=dict(x=[threshold_init, threshold_init], y=[0, max(y_healthy.max(), y_diseased.max())]))
source_roc = ColumnDataSource(data=dict(x=fpr, y=tpr))
source_current = ColumnDataSource(data=dict(x=[1 - specificity], y=[sensitivity]))

# Create plots
dist_plot = figure(width=300, height=250, title="Test Result Distributions",
                   x_axis_label="Test Value", y_axis_label="Probability Density")
roc_plot = figure(width=300, height=250, title=f"ROC Curve (AUC = {auc:.3f})",
                  x_axis_label="False Positive Rate (1 - Specificity)",
                  y_axis_label="True Positive Rate (Sensitivity)",
                  x_range=(0, 1), y_range=(0, 1))

# Distribution plot
dist_plot.line('x', 'y', source=source_healthy, line_width=2, color='#3498db', legend_label='Healthy')
dist_plot.line('x', 'y', source=source_diseased, line_width=2, color='#e74c3c', legend_label='Diseased')
dist_plot.line('x', 'y', source=source_threshold, line_width=3, line_dash='dashed', color='#27ae60', legend_label='Threshold')

# ROC plot
roc_plot.line('x', 'y', source=source_roc, line_width=3, color='#9b59b6', legend_label='ROC Curve')
roc_plot.line([0, 1], [0, 1], line_width=2, line_dash='dashed', color='#95a5a6', legend_label='Random Guess')
roc_plot.scatter('x', 'y', source=source_current, size=12, color='#27ae60', legend_label='Current')

# Metrics display - split into two divs (one blue + one red in each)
metrics_div_1 = Div(text=f"""
<div style="display: flex; flex-direction: column; gap: 12px; margin: 20px 0;">
    <div style="background: #ecf0f1; padding: 12px; border-radius: 6px; border-left: 4px solid #3498db;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">SENSITIVITY<br>(TPR)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">{sensitivity*100:.1f}%</div>
    </div>
    <div style="background: #ffe5e5; padding: 12px; border-radius: 6px; border-left: 4px solid #e74c3c;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">PRECISION<br>(PPV)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">{ppv*100:.1f}%</div>
    </div>
</div>
""", sizing_mode='stretch_width')

metrics_div_2 = Div(text=f"""
<div style="display: flex; flex-direction: column; gap: 12px; margin: 20px 0;">
    <div style="background: #ecf0f1; padding: 12px; border-radius: 6px; border-left: 4px solid #3498db;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">SPECIFICITY<br>(TNR)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">{specificity*100:.1f}%</div>
    </div>
    <div style="background: #ffe5e5; padding: 12px; border-radius: 6px; border-left: 4px solid #e74c3c;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">NEG PRED VAL<br>(NPV)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">{npv*100:.1f}%</div>
    </div>
</div>
""", sizing_mode='stretch_width')

# Sliders
threshold_slider = Slider(start=-3, end=3, value=threshold_init, step=0.1, title="Diagnostic Threshold", width=150)
separation_slider = Slider(start=0.5, end=3.0, value=separation_init, step=0.1, title="Distribution Separation (Cohen's d)", width=150)
prevalence_slider = Slider(start=1, end=50, value=prevalence_init, step=1, title="Disease Prevalence (%)", width=150)

# JavaScript callback
callback = CustomJS(args=dict(
    source_healthy=source_healthy,
    source_diseased=source_diseased,
    source_threshold=source_threshold,
    source_roc=source_roc,
    source_current=source_current,
    metrics_div_1=metrics_div_1,
    metrics_div_2=metrics_div_2,
    roc_plot=roc_plot,
    threshold_slider=threshold_slider,
    separation_slider=separation_slider,
    prevalence_slider=prevalence_slider
), code="""
    const threshold = threshold_slider.value;
    const separation = separation_slider.value;
    const prevalence = prevalence_slider.value / 100;

    const mean_healthy = 0;
    const mean_diseased = separation;
    const std = 1;

    function normalCDF(x, mean, std) {
        const z = (x - mean) / std;
        const t = 1 / (1 + 0.2316419 * Math.abs(z));
        const d = 0.3989423 * Math.exp(-z * z / 2);
        const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
        return z > 0 ? 1 - p : p;
    }

    function normalPDF(x, mean, std) {
        return (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((x - mean) / std, 2));
    }

    const x = source_healthy.data.x;
    const y_healthy = [];
    const y_diseased = [];
    for (let i = 0; i < x.length; i++) {
        y_healthy.push(normalPDF(x[i], mean_healthy, std));
        y_diseased.push(normalPDF(x[i], mean_diseased, std));
    }
    source_healthy.data.y = y_healthy;
    source_diseased.data.y = y_diseased;

    const max_y = Math.max(...y_healthy, ...y_diseased);
    source_threshold.data = {x: [threshold, threshold], y: [0, max_y]};

    const sensitivity = 1 - normalCDF(threshold, mean_diseased, std);
    const specificity = normalCDF(threshold, mean_healthy, std);
    const ppv = (sensitivity * prevalence) / (sensitivity * prevalence + (1 - specificity) * (1 - prevalence));
    const npv = (specificity * (1 - prevalence)) / ((1 - sensitivity) * prevalence + specificity * (1 - prevalence));

    const fpr = [];
    const tpr = [];
    for (let t = -3; t <= separation + 3; t += 0.06) {
        tpr.push(1 - normalCDF(t, mean_diseased, std));
        fpr.push(1 - normalCDF(t, mean_healthy, std));
    }
    source_roc.data = {x: fpr, y: tpr};

    let auc = 0;
    for (let i = 1; i < fpr.length; i++) {
        const dx = fpr[i-1] - fpr[i];
        const avgY = (tpr[i-1] + tpr[i]) / 2;
        auc += dx * avgY;
    }

    source_current.data = {x: [1 - specificity], y: [sensitivity]};
    roc_plot.title.text = `ROC Curve (AUC = ${auc.toFixed(3)})`;

    metrics_div_1.text = `
<div style="display: flex; flex-direction: column; gap: 12px; margin: 20px 0;">
    <div style="background: #ecf0f1; padding: 12px; border-radius: 6px; border-left: 4px solid #3498db;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">SENSITIVITY<br>(TPR)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">${(sensitivity*100).toFixed(1)}%</div>
    </div>
    <div style="background: #ffe5e5; padding: 12px; border-radius: 6px; border-left: 4px solid #e74c3c;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">PRECISION<br>(PPV)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">${(ppv*100).toFixed(1)}%</div>
    </div>
</div>
`;

    metrics_div_2.text = `
<div style="display: flex; flex-direction: column; gap: 12px; margin: 20px 0;">
    <div style="background: #ecf0f1; padding: 12px; border-radius: 6px; border-left: 4px solid #3498db;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">SPECIFICITY<br>(TNR)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">${(specificity*100).toFixed(1)}%</div>
    </div>
    <div style="background: #ffe5e5; padding: 12px; border-radius: 6px; border-left: 4px solid #e74c3c;">
        <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">NEG PRED VAL<br>(NPV)</div>
        <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">${(npv*100).toFixed(1)}%</div>
    </div>
</div>
`;
""")

threshold_slider.js_on_change('value', callback)
separation_slider.js_on_change('value', callback)
prevalence_slider.js_on_change('value', callback)

# Layout
sliders_col = column(threshold_slider, separation_slider, prevalence_slider)
controls_row = row(sliders_col, metrics_div_1, metrics_div_2)
plots_row = row(dist_plot, roc_plot)
layout = column(controls_row, plots_row)

# Generate components (script and div)
script, div = components(layout)

# Write to HTML file with INLINE resources
with open('/Users/leo.torres/aris/press/seed_papers/roc_curve_widget.html', 'w') as f:
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

print("ROC curve widget generated successfully")
