use std::collections::HashMap;

use eunoia::geometry::primitives::Point;
use eunoia::geometry::shapes::{Circle, Ellipse, Polygon, Rectangle, RotatedRectangle, Square};
use eunoia::geometry::traits::{DiagramShape, Polygonize};
use eunoia::loss::LossType;
use eunoia::plotting::{
    ElbowOptions, ExteriorPolicy, GlyphArrangement, GlyphBoxOptions, GlyphOptions, LabelPlacement,
    LeaderStrategy, PlacementKind, PlacementStrategy, PlotOptions, RegionPiece, RegionPolygons,
    SetLabelStrategy, TetherSource, classify_into_pieces, place_glyph_boxes, place_glyphs,
    place_labels, place_set_labels,
};
use eunoia::spec::{Combination, DiagramSpec};
use eunoia::{DiagramError, DiagramSpecBuilder, Fitter, InputType, Layout, Optimizer, VennDiagram};
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
        "cma_es" => Ok(Optimizer::CmaEs),
        "cma_es_lm" => Ok(Optimizer::CmaEsLm),
        "trf" => Ok(Optimizer::Trf),
        "cma_es_trf" => Ok(Optimizer::CmaEsTrf),
        "mads" => Ok(Optimizer::Mads),
        other => Err(EunoiaError::new_err(format!(
            "invalid_optimizer: unknown optimizer '{other}'; one of \
             'levenberg_marquardt', 'lbfgs', 'nelder_mead', 'cma_es', 'cma_es_lm', \
             'trf', 'cma_es_trf', 'mads'"
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
    spec: &DiagramSpec,
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

    let requested = PyDict::new(py);
    for (combo, val) in layout.requested() {
        requested.set_item(combo.to_string(), *val)?;
    }
    if let Some(complement) = spec.complement() {
        requested.set_item("", complement)?;
    }
    dict.set_item("requested_exclusive", requested)?;

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

fn ser_rotated_rectangle<'py>(
    py: Python<'py>,
    name: &str,
    s: &RotatedRectangle,
) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("set", name)?;
    d.set_item("x", s.center().x())?;
    d.set_item("y", s.center().y())?;
    d.set_item("width", s.width())?;
    d.set_item("height", s.height())?;
    d.set_item("rotation", s.rotation())?;
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

    fill_metrics(py, spec, layout, &result)?;
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

#[pyfunction]
#[pyo3(signature = (combinations, input_kind, complement=None, seed=None, loss=None, optimizer=None, tolerance=None, n_restarts=None, max_iterations=None, n_threads=None))]
fn _fit_rotated_rectangles<'py>(
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
    let mut fitter = Fitter::<RotatedRectangle>::new(&spec);
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
    build_result(py, &spec, &layout, ser_rotated_rectangle)
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
#[pyo3(signature = (
    n, shape, names=None, complement=None, combinations=None,
    input_kind="exclusive"
))]
fn _venn<'py>(
    py: Python<'py>,
    n: usize,
    shape: &str,
    names: Option<Vec<String>>,
    complement: Option<f64>,
    combinations: Option<Vec<(String, f64)>>,
    input_kind: &str,
) -> PyResult<Bound<'py, PyDict>> {
    if let Some(ref names) = names {
        if names.len() != n {
            return Err(EunoiaError::new_err(format!(
                "invalid_value: expected {n} names, got {}",
                names.len()
            )));
        }
    }
    let result = match shape {
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
        "rotated_rectangle" => {
            let (layout, spec) = venn_layout::<RotatedRectangle>(n, names, complement)?;
            build_result(py, &spec, &layout, ser_rotated_rectangle)
        }
        other => Err(EunoiaError::new_err(format!(
            "invalid_shape: shape must be 'circle', 'ellipse', 'square', \
             'rectangle' or 'rotated_rectangle', got '{other}'"
        ))),
    }?;

    // Venn geometry is canonical and therefore has its own synthetic spec.
    // When the caller supplied quantities, validate and canonicalize those
    // through the same DiagramSpec path as euler(), then replace the synthetic
    // requested values with the user's exclusive counts for glyph rendering.
    let requested = PyDict::new(py);
    if let Some(combinations) = combinations {
        let quantity_spec = build_spec(&combinations, input_kind, complement)?;
        for (combo, value) in quantity_spec.exclusive_areas() {
            requested.set_item(combo.to_string(), *value)?;
        }
        if let Some(value) = quantity_spec.complement() {
            requested.set_item("", value)?;
        }
    }
    result.set_item("requested_exclusive", requested)?;
    Ok(result)
}

/// Place labels in their regions, accounting for label size.
///
/// `rings` maps each canonical region key to a flat list of its boundary rings
/// (every piece's outer ring plus any hole rings, each a list of `(x, y)`
/// vertices); orientation is irrelevant, since the core classifies rings into
/// pieces by containment. `sizes` maps a region key to the `(width, height)` of
/// the label to place there, in diagram coordinates. The result maps each
/// placed region key to `{anchor, kind, tether, leader_end, leader_waypoints}`:
/// interior placements have `tether`/`leader_end` `None` and no waypoints;
/// exterior placements carry the leader geometry the renderer draws as the
/// polyline `tether -> leader_waypoints... -> leader_end`.
fn build_regions(rings: &HashMap<String, Vec<Vec<(f64, f64)>>>) -> RegionPolygons {
    let mut map: HashMap<Combination, Vec<RegionPiece>> = HashMap::new();
    for (combo_str, region_rings) in rings {
        let polys: Vec<Polygon> = region_rings
            .iter()
            .map(|ring| Polygon::new(ring.iter().map(|&(x, y)| Point::new(x, y)).collect()))
            .collect();
        let pieces = classify_into_pieces(polys);
        if pieces.is_empty() {
            continue;
        }
        // `Combination`'s FromStr is infallible.
        let combo: Combination = combo_str.parse().unwrap_or_else(|_| Combination::new(&[]));
        map.insert(combo, pieces);
    }
    RegionPolygons::from_map(map)
}

fn rectangles(values: Option<Vec<(f64, f64, f64, f64)>>) -> Vec<Rectangle> {
    values
        .unwrap_or_default()
        .into_iter()
        .filter(|(x, y, w, h)| {
            x.is_finite() && y.is_finite() && w.is_finite() && h.is_finite() && *w > 0.0 && *h > 0.0
        })
        .map(|(x, y, w, h)| Rectangle::new(Point::new(x, y), w, h))
        .collect()
}

fn parse_arrangement(arrangement: Option<&str>) -> PyResult<GlyphArrangement> {
    match arrangement {
        Some("random") => Ok(GlyphArrangement::Random),
        Some("uniform") | None => Ok(GlyphArrangement::Uniform),
        Some(other) => Err(EunoiaError::new_err(format!(
            "invalid_glyph_arrangement: arrangement must be 'uniform' or 'random', got '{other}'"
        ))),
    }
}

fn placement_to_pydict<'py>(
    py: Python<'py>,
    placement: &LabelPlacement,
) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("anchor", (placement.anchor.x(), placement.anchor.y()))?;
    let kind = match placement.kind {
        PlacementKind::Interior => "interior",
        PlacementKind::ExteriorRaycast => "exterior_raycast",
        PlacementKind::ExteriorForceDirected => "exterior_force_directed",
        PlacementKind::ExteriorElbow => "exterior_elbow",
        PlacementKind::ExteriorMatched => "exterior_matched",
        PlacementKind::ExteriorSet => "exterior_set",
        // `PlacementKind` is #[non_exhaustive].
        _ => "exterior",
    };
    d.set_item("kind", kind)?;
    d.set_item("tether", placement.tether.as_ref().map(|p| (p.x(), p.y())))?;
    d.set_item(
        "leader_end",
        placement.leader_end.as_ref().map(|p| (p.x(), p.y())),
    )?;
    let waypoints = PyList::empty(py);
    for p in &placement.leader_waypoints {
        waypoints.append((p.x(), p.y()))?;
    }
    d.set_item("leader_waypoints", waypoints)?;
    Ok(d)
}

#[pyfunction]
#[pyo3(signature = (
    rings, sizes, container=None, precision=None, exterior=None, tether=None,
    leader_gap=None, margin=None, iterations=None, min_gap=None
))]
#[allow(clippy::too_many_arguments)]
fn _place_labels<'py>(
    py: Python<'py>,
    rings: HashMap<String, Vec<Vec<(f64, f64)>>>,
    sizes: HashMap<String, (f64, f64)>,
    container: Option<(f64, f64, f64, f64)>,
    precision: Option<f64>,
    exterior: Option<&str>,
    tether: Option<&str>,
    leader_gap: Option<f64>,
    margin: Option<f64>,
    iterations: Option<usize>,
    min_gap: Option<f64>,
) -> PyResult<Bound<'py, PyDict>> {
    let regions = build_regions(&rings);

    let leader = match exterior {
        Some("force_directed") => {
            LeaderStrategy::Straight(ExteriorPolicy::ForceDirected { margin, iterations })
        }
        Some("matched") => LeaderStrategy::Straight(ExteriorPolicy::Matched { margin }),
        Some("elbow") => {
            LeaderStrategy::Elbow(ElbowOptions::default().margin(margin).min_gap(min_gap))
        }
        Some("raycast") | None => LeaderStrategy::Straight(ExteriorPolicy::Raycast { margin }),
        Some(other) => {
            return Err(EunoiaError::new_err(format!(
                "invalid_placement: exterior must be 'raycast', 'force_directed', 'matched', or 'elbow', got '{other}'"
            )));
        }
    };
    let tether_source = match tether {
        Some("boundary") => TetherSource::Boundary,
        Some("poi") | None => TetherSource::Poi,
        Some(other) => {
            return Err(EunoiaError::new_err(format!(
                "invalid_placement: tether must be 'poi' or 'boundary', got '{other}'"
            )));
        }
    };
    let mut strategy = PlacementStrategy::default()
        .leader(leader)
        .tether(tether_source);
    if let Some(p) = precision {
        strategy = strategy.precision(p);
    }
    if let Some(g) = leader_gap {
        strategy = strategy.leader_gap(g);
    }

    let container_rect = container.map(|(cx, cy, w, h)| Rectangle::new(Point::new(cx, cy), w, h));

    let placements = place_labels(&regions, &sizes, container_rect.as_ref(), &strategy);

    let out = PyDict::new(py);
    for (combo, placement) in &placements {
        out.set_item(combo, placement_to_pydict(py, placement)?)?;
    }
    Ok(out)
}

#[pyfunction]
#[pyo3(signature = (
    outlines, sizes, container=None, margin=None, angular_steps=None,
    precision=None, obstacles=None
))]
fn _place_set_labels<'py>(
    py: Python<'py>,
    outlines: HashMap<String, Vec<(f64, f64)>>,
    sizes: HashMap<String, (f64, f64)>,
    container: Option<(f64, f64, f64, f64)>,
    margin: Option<f64>,
    angular_steps: Option<usize>,
    precision: Option<f64>,
    obstacles: Option<Vec<(f64, f64, f64, f64)>>,
) -> PyResult<Bound<'py, PyDict>> {
    let polygons: HashMap<String, Polygon> = outlines
        .into_iter()
        .map(|(name, vertices)| {
            let polygon = Polygon::new(
                vertices
                    .into_iter()
                    .map(|(x, y)| Point::new(x, y))
                    .collect(),
            );
            (name, polygon)
        })
        .collect();
    let mut strategy = SetLabelStrategy::default()
        .margin(margin)
        .obstacles(rectangles(obstacles));
    if let Some(steps) = angular_steps {
        strategy = strategy.angular_steps(steps);
    }
    if let Some(value) = precision {
        strategy = strategy.precision(value);
    }
    let container_rect = container.map(|(x, y, w, h)| Rectangle::new(Point::new(x, y), w, h));
    let placements = place_set_labels(&polygons, &sizes, container_rect.as_ref(), &strategy);
    let out = PyDict::new(py);
    for (name, placement) in &placements {
        out.set_item(name, placement_to_pydict(py, placement)?)?;
    }
    Ok(out)
}

#[pyfunction]
#[pyo3(signature = (
    rings, counts, arrangement=None, radius=None, gap=None, seed=None,
    precision=None, max_attempts=None, obstacles=None
))]
#[allow(clippy::too_many_arguments)]
fn _place_glyphs<'py>(
    py: Python<'py>,
    rings: HashMap<String, Vec<Vec<(f64, f64)>>>,
    counts: HashMap<String, usize>,
    arrangement: Option<&str>,
    radius: Option<f64>,
    gap: Option<f64>,
    seed: Option<u64>,
    precision: Option<f64>,
    max_attempts: Option<u32>,
    obstacles: Option<Vec<(f64, f64, f64, f64)>>,
) -> PyResult<Bound<'py, PyDict>> {
    let regions = build_regions(&rings);
    let mut options = GlyphOptions::default()
        .arrangement(parse_arrangement(arrangement)?)
        .radius(radius)
        .obstacles(rectangles(obstacles));
    if let Some(value) = gap {
        options = options.gap(value);
    }
    if let Some(value) = seed {
        options = options.seed(value);
    }
    if let Some(value) = precision {
        options = options.precision(value);
    }
    if let Some(value) = max_attempts {
        options = options.max_attempts(value);
    }
    let placed = place_glyphs(&regions, &counts, &options);
    let out = PyDict::new(py);
    out.set_item("radius", placed.radius)?;
    let positions = PyDict::new(py);
    for (combo, points) in &placed.positions {
        let values: Vec<(f64, f64)> = points.iter().map(|p| (p.x(), p.y())).collect();
        positions.set_item(combo, values)?;
    }
    out.set_item("positions", positions)?;
    out.set_item("unplaced", placed.unplaced)?;
    Ok(out)
}

#[pyfunction]
#[pyo3(signature = (
    rings, sizes, arrangement=None, scale=None, min_scale=None, gap=None,
    seed=None, precision=None, max_attempts=None, obstacles=None
))]
#[allow(clippy::too_many_arguments)]
fn _place_glyph_boxes<'py>(
    py: Python<'py>,
    rings: HashMap<String, Vec<Vec<(f64, f64)>>>,
    sizes: HashMap<String, Vec<(f64, f64)>>,
    arrangement: Option<&str>,
    scale: Option<f64>,
    min_scale: Option<f64>,
    gap: Option<f64>,
    seed: Option<u64>,
    precision: Option<f64>,
    max_attempts: Option<u32>,
    obstacles: Option<Vec<(f64, f64, f64, f64)>>,
) -> PyResult<Bound<'py, PyDict>> {
    let regions = build_regions(&rings);
    let mut options = GlyphBoxOptions::default()
        .arrangement(parse_arrangement(arrangement)?)
        .scale(scale)
        .obstacles(rectangles(obstacles));
    if let Some(value) = min_scale {
        options = options.min_scale(value);
    }
    if let Some(value) = gap {
        options = options.gap(value);
    }
    if let Some(value) = seed {
        options = options.seed(value);
    }
    if let Some(value) = precision {
        options = options.precision(value);
    }
    if let Some(value) = max_attempts {
        options = options.max_attempts(value);
    }
    let placed = place_glyph_boxes(&regions, &sizes, &options);
    let out = PyDict::new(py);
    out.set_item("scale", placed.scale)?;
    let boxes = PyDict::new(py);
    for (combo, rects) in &placed.boxes {
        let values: Vec<(f64, f64, f64, f64)> = rects
            .iter()
            .map(|rect| {
                (
                    rect.center().x(),
                    rect.center().y(),
                    rect.width(),
                    rect.height(),
                )
            })
            .collect();
        boxes.set_item(combo, values)?;
    }
    out.set_item("boxes", boxes)?;
    out.set_item("unplaced", placed.unplaced)?;
    Ok(out)
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
    m.add_function(wrap_pyfunction!(_fit_rotated_rectangles, m)?)?;
    m.add_function(wrap_pyfunction!(_venn, m)?)?;
    m.add_function(wrap_pyfunction!(_place_labels, m)?)?;
    m.add_function(wrap_pyfunction!(_place_set_labels, m)?)?;
    m.add_function(wrap_pyfunction!(_place_glyphs, m)?)?;
    m.add_function(wrap_pyfunction!(_place_glyph_boxes, m)?)?;
    Ok(())
}
