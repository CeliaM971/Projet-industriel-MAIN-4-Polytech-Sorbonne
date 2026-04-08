import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:test_import_video/MediaPipe/mediapipe_service.dart';
import 'dart:math';
import '../MediaPipe/constants.dart';

class MotionPlotting{

  //On génère un widget avec les graphiques de position et vitesse
  // C'est l'équivalent de plotAndExcelSave() du code python sans sauvegarde Excel
  static Widget buildMotionPlots({
    required String plot_name,
    required MotionData motion_data,
    required Color plot_color,
    required MotionType motion_type,
    required bool is_limit_option_selected,
    double limit_max = -1000,
    double limit_min = -1000,
    double zoom_start = -1,
    double zoom_end = -1,
    double threshold_max = -1000,
    double threshold_min = -1000,
  }) {

    if (motion_data.times.isEmpty || motion_data.values.isEmpty) {
      return const Center(child:Text('Aucune donnée à afficher'));
    }

    final velocity_dataframe = _calculateVelocity(motion_data);

    return Column(
      children: [
        // Graphique principal
        _buildMainPlot(
          plot_name: plot_name,
          motion_data: motion_data,
          plot_color: plot_color,
          motion_type: motion_type,
          is_limit_option_selected: is_limit_option_selected,
          limit_max: limit_max,
          limit_min: limit_min,
          zoom_start: zoom_start,
          zoom_end: zoom_end,
          threshold_max: threshold_max,
          threshold_min: threshold_min,
        ),

        const SizedBox(height: 24),
        
        // Graphique de vitesse
        _buildVelocityPlot(
          plot_name: plot_name,
          velocity_dataframe: velocity_dataframe,
          plot_color: plot_color,
          isBilateral: motion_data.isBilateral,
          zoom_start: zoom_start,
          zoom_end: zoom_end,
        ),
      ],
    );
  }

  ///Graphique principal(position)
  static Widget _buildMainPlot({
    required String plot_name,
    required MotionData motion_data,
    required Color plot_color,
    required MotionType motion_type,
    required bool is_limit_option_selected,
    required double limit_max,
    required double limit_min,
    required double zoom_start,
    required double zoom_end,
    required double threshold_max,
    required double threshold_min,
  }) {

    // Détermination des limites par défaut (équivalent Python)
    double limit_max_local = limit_max;
    double limit_min_local = limit_min;

    if (limit_max == -1000 && limit_min == -1000) {
      switch (motion_type) {
        case MotionType.HEAD_ABDADD:
          limit_max_local = 60;
          limit_min_local = -60;
          break;
        case MotionType.HEAD_FLXEXT:
        case MotionType.HEAD_ROTATION:
          limit_max_local = 0.5;
          limit_min_local = -0.5;
          break;
        case MotionType.SHOULDER_ABDADD:
        case MotionType.SHOULDER_FLXEXT:
        case MotionType.TORSO_ABDADD:
          limit_max_local = 1;
          limit_min_local = 0;
          break;
        case MotionType.HEAD_ROT_LAT:
        case MotionType.TORSO_FLXEXT:
          limit_max_local = 50;
          limit_min_local = -50;
          break;
        case MotionType.TORSO_ROTATION:
          limit_max_local = 3;
          limit_min_local = -3;
          break;
        case MotionType.ARM_ABDADD:
        case MotionType.ARM_FLXEXT:
        case MotionType.ARM_FLXEXT_LAT:
        case MotionType.FOREARM_FLXEXT:
          limit_max_local = 180;
          limit_min_local = 0;
          break;
      }
    }

    double y_max = motion_data.values.reduce(max);
    double y_min = motion_data.values.reduce(min);

    if(motion_data.isBilateral){
      y_max = max(y_max, motion_data.valuesLeft!.reduce(max));
      y_min = min(y_min, motion_data.valuesLeft!.reduce(min));
    }

    // ── Build extra (horizontal reference) lines ─────────────────────────────
    final extraLines = <HorizontalLine>[
      ..._neutralLines(motion_type, y_min, limit_min_local),
      if (is_limit_option_selected) ...[
        HorizontalLine(
          y: max(y_max, limit_max_local),
          color: Colors.green,
          strokeWidth: 2,
          dashArray: [5, 5],
          label: HorizontalLineLabel(
            show: true,
            labelResolver: (_) => 'Limite max',
            style: const TextStyle(fontSize: 10, color: Colors.green),
          ),
        ),
        HorizontalLine(
          y: min(y_min, limit_min_local),
          color: Colors.blue,
          strokeWidth: 2,
          dashArray: [5, 5],
          label: HorizontalLineLabel(
            show: true,
            labelResolver: (_) => 'Limite min',
            style: const TextStyle(fontSize: 10, color: Colors.blue),
          ),
        ),
      ],
      if (threshold_max != -1000)
        HorizontalLine(
          y: threshold_max,
          color: Colors.red,
          strokeWidth: 2,
          dashArray: [10, 5],
          label: HorizontalLineLabel(
            show: true,
            labelResolver: (_) => 'Seuil max',
            style: const TextStyle(fontSize: 10, color: Colors.red),
          ),
        ),
      if (threshold_min != -1000)
        HorizontalLine(
          y: threshold_min,
          color: Colors.pink,
          strokeWidth: 2,
          dashArray: [10, 5],
          label: HorizontalLineLabel(
            show: true,
            labelResolver: (_) => 'Seuil min',
            style: const TextStyle(fontSize: 10, color: Colors.pink),
          ),
        ),
    ];

    // ── Line series ──────────────────────────────────────────────────────────
    final lineBars = <LineChartBarData>[
      LineChartBarData(
        spots: _toSpots(motion_data.times, motion_data.values),
        isCurved: false,
        color: plot_color,
        barWidth: 2,
        dotData: const FlDotData(show: false),
      ),
      if (motion_data.isBilateral)
        LineChartBarData(
          spots: _toSpots(motion_data.times, motion_data.valuesLeft!),
          isCurved: false,
          color: _invertColor(plot_color),
          barWidth: 2,
          dotData: const FlDotData(show: false),
        ),
    ];

    // ── Zoom ─────────────────────────────────────────────────────────────────
    final double? minX = zoom_end != -1 ? zoom_end : null;
    final double? maxX = zoom_start != -1 ? zoom_start : null;

    return _chartCard(
      title: 'Courbe $plot_name',
      titleColor: plot_color,
      isBilateral: motion_data.isBilateral,
      plotColor: plot_color,
      child: LineChart(
        LineChartData(
          minX: minX,
          maxX: maxX,
          gridData: const FlGridData(show: true),
          borderData: FlBorderData(show: true),
          titlesData: FlTitlesData(
            bottomTitles: AxisTitles(
              axisNameWidget: const Text('Temps [s]',
                  style: TextStyle(fontSize: 12)),
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 30,
                getTitlesWidget: (value, meta) => Text(
                  value.toStringAsFixed(1),
                  style: const TextStyle(fontSize: 10),
                ),
              ),
            ),
            leftTitles: AxisTitles(
              axisNameWidget: Text(
                _yAxisLabel(motion_type),
                style: const TextStyle(fontSize: 10),
                textAlign: TextAlign.center,
              ),
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 56,
                getTitlesWidget: (value, meta) => Text(
                  value.toStringAsFixed(1),
                  style: const TextStyle(fontSize: 10),
                ),
              ),
            ),
            topTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          lineBarsData: lineBars,
          extraLinesData: ExtraLinesData(horizontalLines: extraLines),
        ),
      ),
    );
  }

  // ── Velocity chart ─────────────────────────────────────────────────────────

  static Widget _buildVelocityPlot({
    required String plot_name,
    required MotionData velocity_dataframe,
    required Color plot_color,
    required bool isBilateral,
    required double zoom_start,
    required double zoom_end,
  }) {
    final double? minX = zoom_end != -1 ? zoom_end : null;
    final double? maxX = zoom_start != -1 ? zoom_start : null;

    final lineBars = <LineChartBarData>[
      LineChartBarData(
        spots: _toSpots(velocity_dataframe.times, velocity_dataframe.values),
        isCurved: false,
        color: plot_color,
        barWidth: 2,
        dotData: const FlDotData(show: false),
      ),
      if (isBilateral && velocity_dataframe.valuesLeft != null)
        LineChartBarData(
          spots: _toSpots(velocity_dataframe.times, velocity_dataframe.valuesLeft!),
          isCurved: false,
          color: _invertColor(plot_color),
          barWidth: 2,
          dotData: const FlDotData(show: false),
        ),
    ];

    return _chartCard(
      title: 'Courbe vitesse $plot_name',
      titleColor: plot_color,
      isBilateral: isBilateral,
      plotColor: plot_color,
      child: LineChart(
        LineChartData(
          minX: minX,
          maxX: maxX,
          gridData: const FlGridData(show: true),
          borderData: FlBorderData(show: true),
          titlesData: FlTitlesData(
            bottomTitles: AxisTitles(
              axisNameWidget: const Text('Temps [s]',
                  style: TextStyle(fontSize: 12)),
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 30,
                getTitlesWidget: (value, meta) => Text(
                  value.toStringAsFixed(1),
                  style: const TextStyle(fontSize: 10),
                ),
              ),
            ),
            leftTitles: AxisTitles(
              axisNameWidget: const Text('Vitesse [*/s]',
                  style: TextStyle(fontSize: 10)),
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 56,
                getTitlesWidget: (value, meta) => Text(
                  value.toStringAsFixed(1),
                  style: const TextStyle(fontSize: 10),
                ),
              ),
            ),
            topTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          lineBarsData: lineBars,
        ),
      ),
    );
  }

  // ── Velocity computation (matches Python filtreMoyenneur1D logic) ──────────

  static MotionData _calculateVelocity(MotionData data) {
    List<double> vel = List.from(data.values);
    List<double>? velLeft;

    // Discrete derivative
    for (int i = 0; i < vel.length - 1; i++) {
      double dt = data.times[i + 1] - data.times[i];
      if (dt.abs() < 1e-10) dt = 1e-10;
      vel[i] = (data.values[i + 1] - data.values[i]).abs() / dt;
    }
    vel[vel.length - 1] = vel[vel.length - 2];

    if (data.isBilateral) {
      velLeft = List.from(data.valuesLeft!);
      for (int i = 0; i < velLeft.length - 1; i++) {
        double dt = data.times[i + 1] - data.times[i];
        if (dt.abs() < 1e-10) dt = 1e-10;
        velLeft[i] =
            (data.valuesLeft![i + 1] - data.valuesLeft![i]).abs() / dt;
      }
      velLeft[velLeft.length - 1] = velLeft[velLeft.length - 2];
    }

    // Moving average filter
    final windowSize = data.isBilateral ? 7 : 15;
    vel = _movingAverage(vel, windowSize);
    if (velLeft != null) velLeft = _movingAverage(velLeft, windowSize);

    return MotionData(
      times: data.times,
      values: vel,
      valuesLeft: velLeft,
    );
  }

  static List<double> _movingAverage(List<double> data, int size) {
    if (size % 2 == 0) size++;
    final half = size ~/ 2;
    final result = List<double>.from(data);
    for (int i = half; i < data.length - half; i++) {
      result[i] = data.sublist(i - half, i + half + 1).reduce((a, b) => a + b) / size;
    }
    return result;
  }


  // ── Neutral / reference horizontal lines (mirrors Python plt.axhline) ─────

  static List<HorizontalLine> _neutralLines(
      MotionType type, double yMin, double limitMinLocal) {
    HorizontalLine blackDash(double y) => HorizontalLine(
          y: y,
          color: Colors.black,
          strokeWidth: 1,
          dashArray: [5, 5],
        );

    switch (type) {
      case MotionType.HEAD_ABDADD:
      case MotionType.HEAD_ROTATION:
      case MotionType.HEAD_ROT_LAT:
      case MotionType.HEAD_FLXEXT:
      case MotionType.TORSO_ABDADD:
      case MotionType.TORSO_ROTATION:
      case MotionType.ARM_FLXEXT_LAT:
        return [blackDash(0)];

      case MotionType.SHOULDER_ABDADD:
      case MotionType.SHOULDER_FLXEXT:
      case MotionType.ARM_FLXEXT:
        return [blackDash(min(yMin, limitMinLocal))];

      case MotionType.TORSO_FLXEXT:
        return [
          HorizontalLine(
            y: 1,
            color: Colors.green,
            strokeWidth: 1,
          )
        ];

      case MotionType.ARM_ABDADD:
        return [blackDash(90)];

      default:
        return [];
    }
  }

  // ── Y-axis label (mirrors Python YAxisLabel enum) ─────────────────────────

  static String _yAxisLabel(MotionType type) {
    switch (type) {
      case MotionType.HEAD_ABDADD:
      case MotionType.HEAD_ROTATION:
      case MotionType.TORSO_ABDADD:
      case MotionType.TORSO_ROTATION:
        return '<< Gauche  Angle [deg]  Droite >>';
      case MotionType.HEAD_FLXEXT:
      case MotionType.HEAD_ROT_LAT:
      case MotionType.TORSO_FLXEXT:
        return '<< Flex  Angle norm  Ext >>';
      case MotionType.SHOULDER_FLXEXT:
        return '|| Normal  Haussement >>';
      case MotionType.SHOULDER_ABDADD:
        return '<< Abd  Distance  Add >>';
      case MotionType.ARM_ABDADD:
      case MotionType.ARM_FLXEXT:
      case MotionType.ARM_FLXEXT_LAT:
      case MotionType.FOREARM_FLXEXT:
        return '<<  Angle [deg]  >>';
    }
  }

  // ── Map server (limb, action) strings → MotionType ───────────────────

  /// Equivalent of MOTION_TYPE_MAP in main.py.
  static MotionType? fromServerStrings(String limb, String action) {
    const map = <(String, String), MotionType>{
      ('Head', 'Abduction/Adduction'): MotionType.HEAD_ABDADD,
      ('Head', 'Flexion/Extension'): MotionType.HEAD_FLXEXT,
      ('Head', 'Rotation'): MotionType.HEAD_ROTATION,
      ('Shoulder', 'Abduction/Adduction'): MotionType.SHOULDER_ABDADD,
      ('Shoulder', 'Flexion/Extension'): MotionType.SHOULDER_FLXEXT,
      ('Torso', 'Abduction/Adduction'): MotionType.TORSO_ABDADD,
      ('Torso', 'Flexion/Extension'): MotionType.TORSO_FLXEXT,
      ('Torso', 'Rotation'): MotionType.TORSO_ROTATION,
      ('Arm', 'Abduction/Adduction'): MotionType.ARM_ABDADD,
      ('Arm', 'Flexion/Extension'): MotionType.ARM_FLXEXT,
      ('Fore Arm', 'Flexion/Extension'): MotionType.FOREARM_FLXEXT,
    };
    return map[(limb, action)];
  }

  // ── Card shell shared by both charts ──────────────────────────────────────

  static Widget _chartCard({
    required String title,
    required Color titleColor,
    required bool isBilateral,
    required Color plotColor,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: titleColor,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(height: 280, child: child),
          const SizedBox(height: 12),
          _buildLegend(isBilateral: isBilateral, plotColor: plotColor),
        ],
      ),
    );
  }

  // ── Legend ────────────────────────────────────────────────────────────────

  static Widget _buildLegend(
      {required bool isBilateral, required Color plotColor}) {
    if (!isBilateral) {
      return _legendItem('Data', plotColor);
    }
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _legendItem('Droit', plotColor),
        const SizedBox(width: 24),
        _legendItem('Gauche', _invertColor(plotColor)),
      ],
    );
  }

  static Widget _legendItem(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 20, height: 2, color: color),
        const SizedBox(width: 6),
        Text(label,
            style: TextStyle(fontSize: 12, color: Colors.grey[700])),
      ],
    );
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  static List<FlSpot> _toSpots(List<double> times, List<double> values) {
    final len = min(times.length, values.length);
    return List.generate(len, (i) => FlSpot(times[i], values[i]));
  }

  static Color _invertColor(Color c) =>
      Color.fromARGB(c.alpha, 255 - c.red, 255 - c.green, 255 - c.blue);
}



