import 'dart:math';
import 'models.dart';

/// backend/app/features.py-ийн хөнгөн хувилбар: офлайн үед төхөөрөмж дээр ажиллана.
class Stats {
  final int n;
  final double? lastInterval; // минут
  final double? meanInterval; // минут
  final double? meanDuration; // секунд
  final double freqPerHour;
  final double spanMin;
  final double intervalCv;
  const Stats(this.n, this.lastInterval, this.meanInterval, this.meanDuration, this.freqPerHour,
      this.spanMin, this.intervalCv);
}

List<Contraction> clean(List<Contraction> xs) {
  final s = [...xs.where((c) => c.end > c.start)]..sort((a, b) => a.start.compareTo(b.start));
  final out = <Contraction>[];
  for (final c in s) {
    if (c.duration < 10) continue; // санамсаргүй товшилт
    if (out.isNotEmpty && c.start < out.last.end) {
      final p = out.removeLast();
      out.add(Contraction(start: p.start, end: max(p.end, c.end), pain: p.pain ?? c.pain));
      continue;
    }
    out.add(c);
  }
  return out;
}

Stats computeStats(List<Contraction> all, double now) {
  final cs = clean(all);
  final win = cs.where((c) => c.start >= now - 3600).toList();
  if (win.isEmpty) return const Stats(0, null, null, null, 0, 0, 0);
  final iv = <double>[];
  for (var i = 1; i < win.length; i++) {
    iv.add((win[i].start - win[i - 1].start) / 60.0);
  }
  double mean(List<double> a) => a.isEmpty ? 0 : a.reduce((x, y) => x + y) / a.length;
  final mi = iv.isEmpty ? null : mean(iv);
  double cv = 0;
  if (iv.length > 1 && mi != null && mi > 0) {
    final v = iv.map((x) => (x - mi) * (x - mi)).reduce((a, b) => a + b) / (iv.length - 1);
    cv = sqrt(v) / mi;
  }
  final winSec = max(now - win.first.start, 15 * 60.0);
  return Stats(
    win.length,
    iv.isEmpty ? null : iv.last,
    mi,
    mean(win.map((c) => c.duration).toList()),
    win.length / winSec * 3600,
    (now - cs.first.start) / 60.0,
    cv,
  );
}

/// Офлайн аюулгүй дүрэм (backend/app/rules.py-тэй ижил логик).
String offlineRule(List<Contraction> cs, int gaWeek, Set<String> symptoms, double now) {
  if (symptoms.any(kRedFlags.contains)) return 'HIGH';
  final s = computeStats(cs, now);
  if (gaWeek < 37) {
    if (s.freqPerHour >= 6) return 'HIGH';
    if (s.freqPerHour >= 4) return 'MEDIUM';
    return 'LOW';
  }
  final mi = s.meanInterval ?? 99, md = s.meanDuration ?? 0;
  if (s.n >= 3 && mi <= 5 && md >= 60 && s.spanMin >= 60) return 'HIGH';
  if (s.n >= 3 && ((mi <= 5 && md >= 60) || (mi <= 10 && s.intervalCv <= 0.35))) return 'MEDIUM';
  return 'LOW';
}
