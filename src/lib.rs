use eunoia::geometry::shapes::{Circle, Ellipse};
use eunoia::geometry::traits::{DiagramShape, Polygonize};
use eunoia::plotting::PlotOptions;
use eunoia::spec::DiagramSpec;
use eunoia::{DiagramError, DiagramSpecBuilder, Fitter, InputType, Layout};
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

fn build_spec(combinations: &[(String, f64)], input_kind: &str) -> PyResult<DiagramSpec> {
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
    builder.build().map_err(map_err)
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

    let shape_outlines = PyDict::new(py);
    for (name, poly) in &plot.shape_outlines {
        shape_outlines.set_item(name, polygon_to_pylist(py, poly)?)?;
    }
    dict.set_item("shape_outlines", shape_outlines)?;

    Ok(())
}

#[pyfunction]
#[pyo3(signature = (combinations, input_kind, seed=None))]
fn _fit_circles<'py>(
    py: Python<'py>,
    combinations: Vec<(String, f64)>,
    input_kind: &str,
    seed: Option<u64>,
) -> PyResult<Bound<'py, PyDict>> {
    let spec = build_spec(&combinations, input_kind)?;
    let mut fitter = Fitter::<Circle>::new(&spec);
    if let Some(s) = seed {
        fitter = fitter.seed(s);
    }
    let layout = fitter.fit().map_err(map_err)?;

    let result = PyDict::new(py);

    let shapes = PyList::empty(py);
    for (name, shape) in spec.set_names().iter().zip(layout.shapes().iter()) {
        let s = PyDict::new(py);
        s.set_item("set", name)?;
        s.set_item("x", shape.center().x())?;
        s.set_item("y", shape.center().y())?;
        s.set_item("radius", shape.radius())?;
        shapes.append(s)?;
    }
    result.set_item("shapes", shapes)?;

    fill_metrics(py, &layout, &result)?;
    fill_plot_data(py, &spec, &layout, &result)?;
    Ok(result)
}

#[pyfunction]
#[pyo3(signature = (combinations, input_kind, seed=None))]
fn _fit_ellipses<'py>(
    py: Python<'py>,
    combinations: Vec<(String, f64)>,
    input_kind: &str,
    seed: Option<u64>,
) -> PyResult<Bound<'py, PyDict>> {
    let spec = build_spec(&combinations, input_kind)?;
    let mut fitter = Fitter::<Ellipse>::new(&spec);
    if let Some(s) = seed {
        fitter = fitter.seed(s);
    }
    let layout = fitter.fit().map_err(map_err)?;

    let result = PyDict::new(py);

    let shapes = PyList::empty(py);
    for (name, shape) in spec.set_names().iter().zip(layout.shapes().iter()) {
        let s = PyDict::new(py);
        s.set_item("set", name)?;
        s.set_item("x", shape.center().x())?;
        s.set_item("y", shape.center().y())?;
        s.set_item("semi_major", shape.semi_major())?;
        s.set_item("semi_minor", shape.semi_minor())?;
        s.set_item("rotation", shape.rotation())?;
        shapes.append(s)?;
    }
    result.set_item("shapes", shapes)?;

    fill_metrics(py, &layout, &result)?;
    fill_plot_data(py, &spec, &layout, &result)?;
    Ok(result)
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
    Ok(())
}
