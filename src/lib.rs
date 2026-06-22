use eunoia::geometry::shapes::{Circle, Ellipse, Rectangle, Square};
use eunoia::geometry::traits::{DiagramShape, Polygonize};
use eunoia::loss::LossType;
use eunoia::plotting::PlotOptions;
use eunoia::spec::DiagramSpec;
use eunoia::{
    DiagramError, DiagramSpecBuilder, Fitter, InputType, Layout, Optimizer, VennDiagram,
};
use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

create_exception!(_eunoia, EunoiaError, PyValueError);

fn map_err(e: DiagramError) -> PyErr {
    let tag = match &e {
        DiagramError::UndefinedSet(_) => "undefined_set",
        DiagramError::InvalidValue { .. } => "invalid_value",
        DiagramError::EmptySets => "empty_sets",
        DiagramError::DuplicateCombination(_) => "duplicate_combination",
        DiagramError::InvalidCombination(_) => "invalid_combination",
        DiagramError::UnsupportedSetCount(_) => "unsupported_set_count",
        DiagramError::TooManySets { .. } => "too_many_sets",
        DiagramError::InvalidShapeParameter { .. } => "invalid_shape_parameter",
        DiagramError::EmptySolverPool { .. } => "empty_solver_pool",
        // `DiagramError` is #[non_exhaustive]; tag unknown future variants.
        _ => "diagram_error",
    };
    EunoiaError::new_err(format!("{tag}: {e}"))
}

fn parse_input_kind(input_kind: &str) -> PyResult<InputType> {
    match input_kind {
        "exclusive" => Ok(InputType::Exclusive),
        "inclusive" => Ok(InputType::Inclusive),
        other => Err(EunoiaError::new_err(format!(
            "invalid_input: input must be 'exclusive' or 'inclusive', got '{other}'"
        ))),
    }
}

fn parse_loss(loss: &str) -> PyResult<LossType> {
    match loss {
        "sum_squared" => Ok(LossType::SumSquared),
        "sum_absolute" => Ok(LossType::SumAbsolute),
        "sum_squared_region_error" => Ok(LossType::SumSquaredRegionError),
        "sum_absolute_region_error" => Ok(LossType::SumAbsoluteRegionError),
        "max_absolute" => Ok(LossType::MaxAbsolute),
        "max_squared" => Ok(LossType::MaxSquared),
        "root_mean_squared" => Ok(LossType::RootMeanSquared),
        "stress" => Ok(LossType::Stress),
        "diag_error" => Ok(LossType::DiagError),
        "log_sum_absolute" => Ok(LossType::LogSumAbsolute),
        other => Err(EunoiaError::new_err(format!(
            "invalid_loss: unknown loss '{other}'; one of 'sum_squared', \
             'sum_absolute', 'sum_squared_region_error', \
             'sum_absolute_region_error', 'max_absolute', 'max_squared', \
             'root_mean_squared', 'stress', 'diag_error', 'log_sum_absolute'"
        ))),
    }
}

fn parse_optimizer(optimizer: &str) -> PyResult<Optimizer> {
    match optimizer {
        "levenberg_marquardt" => Ok(Optimizer::LevenbergMarquardt),
        "lbfgs" => Ok(Optimizer::Lbfgs),
        "nelder_mead" => Ok(Optimizer::NelderMead),
        "cma_es_lm" => Ok(Optimizer::CmaEsLm),
        "trf" => Ok(Optimizer::Trf),
        "cma_es_trf" => Ok(Optimizer::CmaEsTrf),
        other => Err(EunoiaError::new_err(format!(
            "invalid_optimizer: unknown optimizer '{other}'; one of \
             'levenberg_marquardt', 'lbfgs', 'nelder_mead', 'cma_es_lm', \
             'trf', 'cma_es_trf'"
        ))),
    }
}

fn build_spec(
    combinations: &[(String, f64)],
    input_kind: &str,
    complement: Option<f64>,
) -> PyResult<DiagramSpec> {
    let input_type = parse_input_kind(input_kind)?;
    let mut builder = DiagramSpecBuilder::new().input_type(input_type);
    for (combo_str, value) in combinations {
        let parts: Vec<&str> = combo_str
            .split('&')
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .collect();
        builder = match parts.as_slice() {
            [single] => builder.set(*single, *value),
            many => builder.intersection(many, *value),
        };
    }
    if let Some(c) = complement {
        builder = builder.complement(c);
    }
    builder.build().map_err(map_err)
}

fn fill_container<'py, S>(
    py: Python<'py>,
    layout: &Layout<S>,
    dict: &Bound<'py, PyDict>,
) -> PyResult<()>
where
    S: DiagramShape + Copy + 'static,
{
    match layout.container() {
        Some(rect) => {
            let c = PyDict::new(py);
            c.set_item("x", rect.center().x())?;
            c.set_item("y", rect.center().y())?;
            c.set_item("width", rect.width())?;
            c.set_item("height", rect.height())?;
            dict.set_item("container", c)?;
        }
        None => dict.set_item("container", py.None())?,
    }
    Ok(())
}

fn fill_metrics<'py, S>(
    py: Python<'py>,
    layout: &Layout<S>,
    dict: &Bound<'py, PyDict>,
) -> PyResult<()>
where
    S: DiagramShape + Copy + 'static,
{
    let fitted = PyDict::new(py);
    for (combo, val) in layout.fitted() {
        fitted.set_item(combo.to_string(), *val)?;
    }
    dict.set_item("fitted_exclusive", fitted)?;

    let region_error_dict = PyDict::new(py);
    for (combo, val) in layout.region_error() {
        region_error_dict.set_item(combo.to_string(), val)?;
    }
    dict.set_item("region_error", region_error_dict)?;

    dict.set_item("diag_error", layout.diag_error())?;
    dict.set_item("stress", layout.stress())?;
    dict.set_item("loss", layout.loss())?;
    dict.set_item("iterations", layout.iterations())?;
    Ok(())
}

fn polygon_to_pylist<'py>(
    py: Python<'py>,
    poly: &eunoia::geometry::shapes::Polygon,
) -> PyResult<Bound<'py, PyList>> {
    let list = PyList::empty(py);
    for v in poly.vertices() {
        list.append((v.x(), v.y()))?;
    }
    Ok(list)
}

fn fill_plot_data<'py, S>(
    py: Python<'py>,
    spec: &DiagramSpec,
    layout: &Layout<S>,
    dict: &Bound<'py, PyDict>,
) -> PyResult<()>
where
    S: DiagramShape + Copy + Polygonize + 'static,
{
    let plot = layout.plot_data(spec, PlotOptions::default());

    // Region pieces: dict[combo_str -> list[{"outer": [(x,y),...], "holes": [[(x,y),...]]}]]
    let regions = PyDict::new(py);
    for (combo, pieces) in plot.regions.iter() {
        let pieces_list = PyList::empty(py);
        for piece in pieces {
            let piece_dict = PyDict::new(py);
            piece_dict.set_item("outer", polygon_to_pylist(py, &piece.outer)?)?;
            let holes_list = PyList::empty(py);
            for hole in &piece.holes {
                holes_list.append(polygon_to_pylist(py, hole)?)?;
            }
            piece_dict.set_item("holes", holes_list)?;
            pieces_list.append(piece_dict)?;
        }
        regions.set_item(combo.to_string(), pieces_list)?;
    }
    dict.set_item("region_pieces", regions)?;

    let region_anchors = PyDict::new(py);
    for (combo, point) in &plot.region_anchors {
        region_anchors.set_item(combo, (point.x(), point.y()))?;
    }
    dict.set_item("region_anchors", region_anchors)?;

    let region_areas = PyDict::new(py);
    for (combo, area) in &plot.region_areas {
        region_areas.set_item(combo, area)?;
    }
    dict.set_item("region_areas", region_areas)?;

    let set_anchors = PyDict::new(py);
    for (name, point) in &plot.set_anchors {
        set_anchors.set_item(name, (point.x(), point.y()))?;
    }
    dict.set_item("set_anchors", set_anchors)?;

    // Maps each set to the canonical region string its label anchor was copied
    // from (when it was derived from a region; absent otherwise). The renderer
    // uses this to detect a set-label/region-quantity collision exactly,
    // instead of matching anchor points by float equality.
    let set_anchor_regions = PyDict::new(py);
    for (name, combo) in &plot.set_anchor_regions {
        set_anchor_regions.set_item(name, combo)?;
    }
    dict.set_item("set_anchor_regions", set_anchor_regions)?;

    let shape_outlines = PyDict::new(py);
    for (name, poly) in &plot.shape_outlines {
        shape_outlines.set_item(name, polygon_to_pylist(py, poly)?)?;
    }
    dict.set_item("shape_outlines", shape_outlines)?;

    Ok(())
}

fn ser_circle<'py>(py: Python<'py>, name: &str, s: &Circle) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("set", name)?;
    d.set_item("x", s.center().x())?;
    d.set_item("y", s.center().y())?;
    d.set_item("radius", s.radius())?;
    Ok(d)
}

fn ser_ellipse<'py>(py: Python<'py>, name: &str, s: &Ellipse) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("set", name)?;
    d.set_item("x", s.center().x())?;
    d.set_item("y", s.center().y())?;
    d.set_item("semi_major", s.semi_major())?;
    d.set_item("semi_minor", s.semi_minor())?;
    d.set_item("rotation", s.rotation())?;
    Ok(d)
}

fn ser_square<'py>(py: Python<'py>, name: &str, s: &Square) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("set", name)?;
    d.set_item("x", s.center().x())?;
    d.set_item("y", s.center().y())?;
    d.set_item("side", s.side())?;
    Ok(d)
}

fn ser_rectangle<'py>(py: Python<'py>, name: &str, s: &Rectangle) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("set", name)?;
    d.set_item("x", s.center().x())?;
    d.set_item("y", s.center().y())?;
    d.set_item("width", s.width())?;
    d.set_item("height", s.height())?;
    Ok(d)
}

/// Build the full result dict shared by `_fit_*` and `_venn`: per-set shapes
/// (via `ser`), fit metrics, plot data, and the optional container box.
fn build_result<'py, S, F>(
    py: Python<'py>,
    spec: &DiagramSpec,
    layout: &Layout<S>,
    ser: F,
) -> PyResult<Bound<'py, PyDict>>
where
    S: DiagramShape + Copy + Polygonize + 'static,
    F: Fn(Python<'py>, &str, &S) -> PyResult<Bound<'py, PyDict>>,
{
    let result = PyDict::new(py);

    let shapes = PyList::empty(py);
    for (name, shape) in spec.set_names().iter().zip(layout.shapes().iter()) {
        shapes.append(ser(py, name, shape)?)?;
    }
    result.set_item("shapes", shapes)?;

    fill_metrics(py, layout, &result)?;
    fill_plot_data(py, spec, layout, &result)?;
    fill_container(py, layout, &result)?;
    Ok(result)
}

#[pyfunction]
#[pyo3(signature = (combinations, input_kind, complement=None, seed=None, loss=None, optimizer=None, tolerance=None, n_restarts=None, max_iterations=None, n_threads=None))]
fn _fit_circles<'py>(
    py: Python<'py>,
    combinations: Vec<(String, f64)>,
    input_kind: &str,
    complement: Option<f64>,
    seed: Option<u64>,
    loss: Option<&str>,
    optimizer: Option<&str>,
    tolerance: Option<f64>,
    n_restarts: Option<usize>,
    max_iterations: Option<usize>,
    n_threads: Option<usize>,
) -> PyResult<Bound<'py, PyDict>> {
    let spec = build_spec(&combinations, input_kind, complement)?;
    let mut fitter = Fitter::<Circle>::new(&spec);
    if let Some(s) = seed {
        fitter = fitter.seed(s);
    }
    if let Some(l) = loss {
        fitter = fitter.loss_type(parse_loss(l)?);
    }
    if let Some(o) = optimizer {
        fitter = fitter.optimizer(parse_optimizer(o)?);
    }
    if let Some(t) = tolerance {
        fitter = fitter.tolerance(t);
    }
    if let Some(n) = n_restarts {
        fitter = fitter.n_restarts(n);
    }
    if let Some(m) = max_iterations {
        fitter = fitter.max_iterations(m);
    }
    if let Some(nt) = n_threads {
        fitter = fitter.jobs(nt);
    }
    let layout = fitter.fit().map_err(map_err)?;
    build_result(py, &spec, &layout, ser_circle)
}

#[pyfunction]
#[pyo3(signature = (combinations, input_kind, complement=None, seed=None, loss=None, optimizer=None, tolerance=None, n_restarts=None, max_iterations=None, n_threads=None))]
fn _fit_ellipses<'py>(
    py: Python<'py>,
    combinations: Vec<(String, f64)>,
    input_kind: &str,
    complement: Option<f64>,
    seed: Option<u64>,
    loss: Option<&str>,
    optimizer: Option<&str>,
    tolerance: Option<f64>,
    n_restarts: Option<usize>,
    max_iterations: Option<usize>,
    n_threads: Option<usize>,
) -> PyResult<Bound<'py, PyDict>> {
    let spec = build_spec(&combinations, input_kind, complement)?;
    let mut fitter = Fitter::<Ellipse>::new(&spec);
    if let Some(s) = seed {
        fitter = fitter.seed(s);
    }
    if let Some(l) = loss {
        fitter = fitter.loss_type(parse_loss(l)?);
    }
    if let Some(o) = optimizer {
        fitter = fitter.optimizer(parse_optimizer(o)?);
    }
    if let Some(t) = tolerance {
        fitter = fitter.tolerance(t);
    }
    if let Some(n) = n_restarts {
        fitter = fitter.n_restarts(n);
    }
    if let Some(m) = max_iterations {
        fitter = fitter.max_iterations(m);
    }
    if let Some(nt) = n_threads {
        fitter = fitter.jobs(nt);
    }
    let layout = fitter.fit().map_err(map_err)?;
    build_result(py, &spec, &layout, ser_ellipse)
}

#[pyfunction]
#[pyo3(signature = (combinations, input_kind, complement=None, seed=None, loss=None, optimizer=None, tolerance=None, n_restarts=None, max_iterations=None, n_threads=None))]
fn _fit_squares<'py>(
    py: Python<'py>,
    combinations: Vec<(String, f64)>,
    input_kind: &str,
    complement: Option<f64>,
    seed: Option<u64>,
    loss: Option<&str>,
    optimizer: Option<&str>,
    tolerance: Option<f64>,
    n_restarts: Option<usize>,
    max_iterations: Option<usize>,
    n_threads: Option<usize>,
) -> PyResult<Bound<'py, PyDict>> {
    let spec = build_spec(&combinations, input_kind, complement)?;
    let mut fitter = Fitter::<Square>::new(&spec);
    if let Some(s) = seed {
        fitter = fitter.seed(s);
    }
    if let Some(l) = loss {
        fitter = fitter.loss_type(parse_loss(l)?);
    }
    if let Some(o) = optimizer {
        fitter = fitter.optimizer(parse_optimizer(o)?);
    }
    if let Some(t) = tolerance {
        fitter = fitter.tolerance(t);
    }
    if let Some(n) = n_restarts {
        fitter = fitter.n_restarts(n);
    }
    if let Some(m) = max_iterations {
        fitter = fitter.max_iterations(m);
    }
    if let Some(nt) = n_threads {
        fitter = fitter.jobs(nt);
    }
    let layout = fitter.fit().map_err(map_err)?;
    build_result(py, &spec, &layout, ser_square)
}

#[pyfunction]
#[pyo3(signature = (combinations, input_kind, complement=None, seed=None, loss=None, optimizer=None, tolerance=None, n_restarts=None, max_iterations=None, n_threads=None))]
fn _fit_rectangles<'py>(
    py: Python<'py>,
    combinations: Vec<(String, f64)>,
    input_kind: &str,
    complement: Option<f64>,
    seed: Option<u64>,
    loss: Option<&str>,
    optimizer: Option<&str>,
    tolerance: Option<f64>,
    n_restarts: Option<usize>,
    max_iterations: Option<usize>,
    n_threads: Option<usize>,
) -> PyResult<Bound<'py, PyDict>> {
    let spec = build_spec(&combinations, input_kind, complement)?;
    let mut fitter = Fitter::<Rectangle>::new(&spec);
    if let Some(s) = seed {
        fitter = fitter.seed(s);
    }
    if let Some(l) = loss {
        fitter = fitter.loss_type(parse_loss(l)?);
    }
    if let Some(o) = optimizer {
        fitter = fitter.optimizer(parse_optimizer(o)?);
    }
    if let Some(t) = tolerance {
        fitter = fitter.tolerance(t);
    }
    if let Some(n) = n_restarts {
        fitter = fitter.n_restarts(n);
    }
    if let Some(m) = max_iterations {
        fitter = fitter.max_iterations(m);
    }
    if let Some(nt) = n_threads {
        fitter = fitter.jobs(nt);
    }
    let layout = fitter.fit().map_err(map_err)?;
    build_result(py, &spec, &layout, ser_rectangle)
}

fn venn_layout<S>(
    n: usize,
    names: Option<Vec<String>>,
    complement: Option<f64>,
) -> PyResult<(Layout<S>, DiagramSpec)>
where
    S: DiagramShape + Copy + 'static,
{
    let mut vd = VennDiagram::<S>::new(n).map_err(map_err)?;
    if let Some(c) = complement {
        vd = vd.complement(c).map_err(map_err)?;
    }
    if let Some(names) = names {
        let refs: Vec<&str> = names.iter().map(String::as_str).collect();
        vd = vd.with_names(&refs);
    }
    Ok(vd.into_layout_and_spec())
}

#[pyfunction]
#[pyo3(signature = (n, shape, names=None, complement=None))]
fn _venn<'py>(
    py: Python<'py>,
    n: usize,
    shape: &str,
    names: Option<Vec<String>>,
    complement: Option<f64>,
) -> PyResult<Bound<'py, PyDict>> {
    if let Some(ref names) = names {
        if names.len() != n {
            return Err(EunoiaError::new_err(format!(
                "invalid_value: expected {n} names, got {}",
                names.len()
            )));
        }
    }
    match shape {
        "circle" => {
            let (layout, spec) = venn_layout::<Circle>(n, names, complement)?;
            build_result(py, &spec, &layout, ser_circle)
        }
        "ellipse" => {
            let (layout, spec) = venn_layout::<Ellipse>(n, names, complement)?;
            build_result(py, &spec, &layout, ser_ellipse)
        }
        "square" => {
            let (layout, spec) = venn_layout::<Square>(n, names, complement)?;
            build_result(py, &spec, &layout, ser_square)
        }
        "rectangle" => {
            let (layout, spec) = venn_layout::<Rectangle>(n, names, complement)?;
            build_result(py, &spec, &layout, ser_rectangle)
        }
        other => Err(EunoiaError::new_err(format!(
            "invalid_shape: shape must be 'circle', 'ellipse', 'square' or \
             'rectangle', got '{other}'"
        ))),
    }
}

#[pyfunction]
fn _smoke() -> &'static str {
    "eunoia: scaffolding works"
}

#[pymodule]
fn _eunoia(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("EunoiaError", m.py().get_type::<EunoiaError>())?;
    m.add_function(wrap_pyfunction!(_smoke, m)?)?;
    m.add_function(wrap_pyfunction!(_fit_circles, m)?)?;
    m.add_function(wrap_pyfunction!(_fit_ellipses, m)?)?;
    m.add_function(wrap_pyfunction!(_fit_squares, m)?)?;
    m.add_function(wrap_pyfunction!(_fit_rectangles, m)?)?;
    m.add_function(wrap_pyfunction!(_venn, m)?)?;
    Ok(())
}
