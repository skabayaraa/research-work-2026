import 'dart:async';
import 'dart:math';
import 'dart:ui' show FontFeature;

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'analysis.dart';
import 'api.dart';
import 'models.dart';

void main() => runApp(const AgshiltApp());

double nowSec() => DateTime.now().millisecondsSinceEpoch / 1000.0;

/// Аппын нийтлэг төлөв: агшилтын жагсаалт, идэвхтэй агшилт, тохиргоо.
class AppState extends ChangeNotifier {
  List<Contraction> contractions = [];
  double? activeStart;
  int gaWeek = 38;
  String contactNumber = '';

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    final s = p.getString('contractions');
    if (s != null) contractions = Contraction.decodeList(s);
    gaWeek = p.getInt('ga_week') ?? 38;
    contactNumber = p.getString('contact') ?? '';
    notifyListeners();
  }

  Future<void> _save() async {
    final p = ~await SharedPreferences.getInstance();
    await p.setString('contractions', Contraction.encodeList(contractions));
    await p.setInt('ga_week', gaWeek);
    await p.setString('contact', contactNumber);
  }

  void toggle(int pain) {
    if (activeStart == null) {
      activeStart = nowSec();
    } else {
      contractions.add(
        Contraction(start: activeStart!, end: nowSec(), pain: pain),
      );
      activeStart = null;
      _save();
    }
    notifyListeners();
  }

  void setGa(int w) {
    gaWeek = w;
    _save();
    notifyListeners();
  }

  void setContact(String n) {
    contactNumber = n;
    _save();
  }

  void clearAll() {
    contractions = [];
    _save();
    notifyListeners();
  }
}

class AgshiltApp extends StatelessWidget {
  const AgshiltApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Агшилт AI',
    theme: ThemeData(
      colorSchemeSeed: const Color(0xFF0F766E),
      useMaterial3: true,
    ),
    home: const HomeShell(),
  );
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  final state = AppState();
  final api = Api();
  int tab = 0;

  @override
  void initState() {
    super.initState();
    state.load();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      TimerScreen(state: state, api: api),
      HistoryScreen(state: state),
      SosScreen(state: state),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('Агшилт AI')),
      body: SafeArea(child: pages[tab]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (i) => setState(() => tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.timer), label: 'Таймер'),
          NavigationDestination(icon: Icon(Icons.show_chart), label: 'Түүх'),
          NavigationDestination(icon: Icon(Icons.sos), label: 'Яаралтай'),
        ],
      ),
    );
  }
}

// ======================================================================== ТАЙМЕР
class TimerScreen extends StatefulWidget {
  final AppState state;
  final Api api;
  const TimerScreen({super.key, required this.state, required this.api});
  @override
  State<TimerScreen> createState() => _TimerScreenState();
}

class _TimerScreenState extends State<TimerScreen> {
  Timer? ticker;
  int pain = 5;
  final symptoms = <String>{};
  final textCtl = TextEditingController();
  Assessment? result;
  bool loading = false;

  @override
  void initState() {
    super.initState();
    ticker = Timer.periodic(
      const Duration(milliseconds: 250),
      (_) => setState(() {}),
    );
  }

  @override
  void dispose() {
    ticker?.cancel();
    textCtl.dispose();
    super.dispose();
  }

  String fmt(double s) =>
      '${(s ~/ 60).toString().padLeft(2, '0')}:${(s.toInt() % 60).toString().padLeft(2, '0')}';

  Future<void> runAssess() async {
    setState(() => loading = true);
    final st = widget.state;
    Assessment a;
    try {
      a = await widget.api.assess(
        gaWeek: st.gaWeek,
        contractions: st.contractions,
        symptoms: symptoms,
        freeText: textCtl.text,
      );
    } catch (_) {
      // Сүлжээгүй үед төхөөрөмж дээрх аюулгүй дүрмээр
      a = Assessment(
        level: offlineRule(st.contractions, st.gaWeek, symptoms, nowSec()),
        advice: 'Офлайн горим: энгийн дүрмээр тооцоолов.',
        offline: true,
      );
    }
    setState(() {
      result = a;
      loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.state,
      builder: (context, _) {
        final st = widget.state;
        final s = computeStats(st.contractions, nowSec());
        final running = st.activeStart != null;
        final clock = running
            ? nowSec() - st.activeStart!
            : (st.contractions.isEmpty
                  ? 0.0
                  : nowSec() - st.contractions.last.start);
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Text(
                      running
                          ? 'Агшилт үргэлжилж байна'
                          : 'Агшилт эхлэхэд дарна уу',
                    ),
                    Text(
                      fmt(clock),
                      style: const TextStyle(
                        fontSize: 48,
                        fontWeight: FontWeight.bold,
                        fontFeatures: [FontFeature.tabularFigures()],
                      ),
                    ),
                    SizedBox(
                      width: double.infinity,
                      height: 64,
                      child: FilledButton(
                        style: FilledButton.styleFrom(
                          backgroundColor: running ? Colors.red.shade700 : null,
                        ),
                        onPressed: () => st.toggle(pain),
                        child: Text(
                          running ? 'ДУУССАН' : 'ЭХЭЛСЭН',
                          style: const TextStyle(fontSize: 22),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        _stat(
                          'Сүүлийн интервал',
                          s.lastInterval == null
                              ? '–'
                              : '${s.lastInterval!.toStringAsFixed(1)}м',
                        ),
                        _stat(
                          'Дундаж интервал',
                          s.meanInterval == null
                              ? '–'
                              : '${s.meanInterval!.toStringAsFixed(1)}м',
                        ),
                        _stat(
                          'Дундаж үргэлжлэх',
                          s.meanDuration == null
                              ? '–'
                              : '${s.meanDuration!.round()}с',
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Өвдөлтийн түвшин: $pain/10'),
                    Slider(
                      value: pain.toDouble(),
                      min: 1,
                      max: 10,
                      divisions: 9,
                      onChanged: (v) => setState(() => pain = v.round()),
                    ),
                    const Text('Шинж тэмдэг'),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final e in kSymptoms.entries)
                          FilterChip(
                            label: Text(e.value),
                            selected: symptoms.contains(e.key),
                            onSelected: (on) => setState(
                              () => on
                                  ? symptoms.add(e.key)
                                  : symptoms.remove(e.key),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: textCtl,
                      maxLines: 3,
                      maxLength: 1000,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        labelText: 'Өөрийн үгээр бичих (заавал биш)',
                      ),
                    ),
                    Row(
                      children: [
                        const Text('Жирэмсний долоо хоног: '),
                        DropdownButton<int>(
                          value: st.gaWeek,
                          items: [
                            for (var w = 20; w <= 42; w++)
                              DropdownMenuItem(value: w, child: Text('$w')),
                          ],
                          onChanged: (w) => st.setGa(w ?? 38),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            FilledButton.tonal(
              onPressed: loading ? null : runAssess,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Text(loading ? 'Тооцоолж байна…' : 'Үнэлгээ харах'),
              ),
            ),
            if (result != null)
              ResultCard(result: result!, onSos: () => confirmSos(context, st)),
          ],
        );
      },
    );
  }

  Widget _stat(String label, String value) => Expanded(
    child: Container(
      margin: const EdgeInsets.all(3),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        children: [
          Text(
            value,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11),
          ),
        ],
      ),
    ),
  );
}

class ResultCard extends StatelessWidget {
  final Assessment result;
  final VoidCallback onSos;
  const ResultCard({super.key, required this.result, required this.onSos});

  @override
  Widget build(BuildContext context) {
    const names = {'LOW': 'БАГА', 'MEDIUM': 'ДУНД', 'HIGH': 'ӨНДӨР'};
    final color = {
      'LOW': Colors.green.shade700,
      'MEDIUM': Colors.orange.shade800,
      'HIGH': Colors.red.shade700,
    }[result.level]!;
    return Card(
      margin: const EdgeInsets.only(top: 12),
      shape: RoundedRectangleBorder(
        side: BorderSide(color: color, width: 2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Анхаарах түвшин'),
            Text(
              names[result.level]!,
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.w800,
                color: color,
              ),
            ),
            Text(result.advice),
            for (final e in result.explanations) Text('• $e'),
            if (result.nlpSymptoms.isNotEmpty)
              Text(
                'Бичвэрээс танигдсан: ${result.nlpSymptoms.map((s) => kSymptoms[s] ?? s).join(', ')}',
                style: const TextStyle(fontSize: 12),
              ),
            const SizedBox(height: 6),
            Text(
              '${result.disclaimer}${result.rttMs != null ? ' · ${result.rttMs} мс' : ''}',
              style: const TextStyle(fontSize: 12, color: Colors.black54),
            ),
            if (result.level == 'HIGH')
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.red.shade700,
                  ),
                  onPressed: onSos,
                  child: const Text('Яаралтай холбоо барих хүнд мэдэгдэх'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// ======================================================================== ТҮҮХ
class HistoryScreen extends StatelessWidget {
  final AppState state;
  const HistoryScreen({super.key, required this.state});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: state,
    builder: (context, _) {
      final cs = state.contractions;
      final recent = cs.length > 20 ? cs.sublist(cs.length - 20) : cs;
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Интервал (цэнхэр, мин) ба үргэлжлэх (улбар, с)'),
          SizedBox(
            height: 160,
            child: CustomPaint(
              painter: TrendPainter(recent),
              size: Size.infinite,
            ),
          ),
          const Divider(),
          for (final c in cs.reversed.take(30))
            ListTile(
              dense: true,
              title: Text(
                TimeOfDay.fromDateTime(
                  DateTime.fromMillisecondsSinceEpoch((c.start * 1000).round()),
                ).format(context),
              ),
              subtitle: Text(
                '${c.duration.round()} с · өвдөлт ${c.pain ?? '–'}',
              ),
            ),
          OutlinedButton(
            onPressed: state.clearAll,
            child: const Text('Бүгдийг устгах'),
          ),
        ],
      );
    },
  );
}

class TrendPainter extends CustomPainter {
  final List<Contraction> cs;
  TrendPainter(this.cs);

  @override
  void paint(Canvas canvas, Size size) {
    if (cs.length < 2) return;
    final iv = [
      for (var i = 1; i < cs.length; i++)
        (cs[i].start - cs[i - 1].start) / 60.0,
    ];
    final d = cs.map((c) => c.duration).toList();
    void line(List<double> v, double maxV, Color col) {
      final p = Paint()
        ..color = col
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke;
      final path = Path();
      for (var i = 0; i < v.length; i++) {
        final x = 8 + i * (size.width - 16) / max(1, v.length - 1);
        final y = size.height - 8 - (v[i] / maxV) * (size.height - 16);
        i == 0 ? path.moveTo(x, y) : path.lineTo(x, y);
      }
      canvas.drawPath(path, p);
    }

    line(iv, max(iv.reduce(max), 10), const Color(0xFF2A78D6));
    line(d, max(d.reduce(max), 90), const Color(0xFFEB6834));
  }

  @override
  bool shouldRepaint(covariant TrendPainter old) => old.cs.length != cs.length;
}

// ======================================================================== ЯАРАЛТАЙ
Future<void> confirmSos(BuildContext context, AppState st) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: const Text('Баталгаажуулах'),
      content: const Text(
        'Яаралтай холбоо барих хүнд байршил болон мессеж илгээх үү?',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(c, false),
          child: const Text('Үгүй'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(c, true),
          child: const Text('Тийм, илгээх'),
        ),
      ],
    ),
  );
  if (ok != true) return; // хэрэглэгчийн баталгаажуулалтгүйгээр юу ч илгээхгүй
  String loc = '';
  try {
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied)
      perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.always ||
        perm == LocationPermission.whileInUse) {
      final p = await Geolocator.getCurrentPosition().timeout(
        const Duration(seconds: 6),
      );
      loc = ' Байршил: https://maps.google.com/?q=${p.latitude},${p.longitude}';
    }
  } catch (_) {
    /* байршилгүйгээр үргэлжлүүлнэ */
  }
  final msg = Uri.encodeComponent('Надад тусламж хэрэгтэй байна.$loc');
  await launchUrl(Uri.parse('sms:${st.contactNumber}?body=$msg'));
}

class SosScreen extends StatefulWidget {
  final AppState state;
  const SosScreen({super.key, required this.state});
  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen> {
  late final ctl = TextEditingController(text: widget.state.contactNumber);

  @override
  void dispose() {
    ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      TextField(
        controller: ctl,
        keyboardType: TextInputType.phone,
        decoration: const InputDecoration(
          border: OutlineInputBorder(),
          labelText: 'Яаралтай холбоо барих хүний утас',
        ),
        onChanged: widget.state.setContact,
      ),
      const SizedBox(height: 8),
      const Text(
        'Мессеж зөвхөн таны баталгаажуулсны дараа илгээгдэнэ. Байршлыг зөвшөөрлөөр л авна.',
      ),
      const SizedBox(height: 12),
      FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: Colors.red.shade700,
          minimumSize: const Size.fromHeight(56),
        ),
        onPressed: () => confirmSos(context, widget.state),
        child: const Text('Тусламж хүсэх'),
      ),
      const SizedBox(height: 8),
      OutlinedButton(
        style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        onPressed: () => launchUrl(Uri.parse('tel:103')),
        child: const Text('103 руу залгах'),
      ),
      const SizedBox(height: 16),
      const Text(
        'Энэ апп эмнэлгийн онош тавихгүй. Судалгааны прототип.',
        style: TextStyle(color: Colors.black54),
      ),
    ],
  );
}
