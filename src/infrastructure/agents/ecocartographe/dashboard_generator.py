"""
Générateur de Dashboard Interactif Complet
Combine carte, graphe, statistiques et visualisations avancées
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Acteur, AnalyseReseau, Relation


class DashboardGenerator:
    """Génère un dashboard HTML interactif complet"""

    def __init__(self, output_dir: str = "./workspace/outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generer_dashboard(
        self,
        projet_nom: str,
        acteurs: list[Acteur],
        relations: list[Relation],
        analyse: AnalyseReseau,
        fichier_carte: str,
        fichier_graphe: str,
        nom_fichier: str = "dashboard.html",
    ) -> str:
        """Génère un dashboard HTML complet et interactif"""

        # Préparer les données pour les graphiques
        stats = self._calculer_statistiques(acteurs, relations, analyse)
        acteurs_json = self._acteurs_to_json(acteurs)
        relations_json = self._relations_to_json(relations)

        # Générer le HTML
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{projet_nom} - Dashboard EcoCartographe</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- Bootstrap Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">

    <!-- Plotly -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>

    <!-- DataTables -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css">

    <style>
        :root {{
            --primary-color: #667eea;
            --secondary-color: #764ba2;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
        }}

        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .dashboard-container {{
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}

        .metric-card {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            border: 2px solid #e0e0e0;
            transition: all 0.3s;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}

        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            border-color: var(--primary-color);
        }}

        .metric-value {{
            font-size: 2.5rem;
            font-weight: bold;
            color: var(--primary-color);
        }}

        .metric-label {{
            font-size: 0.9rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .metric-icon {{
            font-size: 3rem;
            opacity: 0.2;
            position: absolute;
            right: 20px;
            top: 50%;
            transform: translateY(-50%);
        }}

        .chart-container {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}

        .visualization-frame {{
            border: none;
            border-radius: 10px;
            width: 100%;
            height: 600px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}

        .nav-tabs .nav-link {{
            color: var(--primary-color);
            font-weight: 600;
        }}

        .nav-tabs .nav-link.active {{
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            color: white;
            border: none;
        }}

        .badge-type {{
            font-size: 0.8rem;
            padding: 5px 12px;
            border-radius: 20px;
        }}

        .table-hover tbody tr:hover {{
            background-color: #f8f9fa;
            cursor: pointer;
        }}

        .progress-bar-animated {{
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
        }}

        .legend-item {{
            display: inline-block;
            margin-right: 15px;
            margin-bottom: 10px;
        }}

        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 5px;
            vertical-align: middle;
        }}

        @media print {{
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container-fluid dashboard-container">
        <!-- Header -->
        <div class="header">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h1 class="mb-2">
                        <i class="bi bi-geo-alt"></i> {projet_nom}
                    </h1>
                    <p class="mb-0">
                        <i class="bi bi-calendar"></i> Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")}
                    </p>
                </div>
                <div class="col-md-4 text-end no-print">
                    <button class="btn btn-light me-2" onclick="window.print()">
                        <i class="bi bi-printer"></i> Imprimer
                    </button>
                    <button class="btn btn-light" onclick="exportData()">
                        <i class="bi bi-download"></i> Exporter
                    </button>
                </div>
            </div>
        </div>

        <!-- Métriques Clés -->
        <div class="row mb-4">
            <div class="col-md-3 col-sm-6">
                <div class="metric-card position-relative">
                    <i class="bi bi-people metric-icon"></i>
                    <div class="metric-value">{len(acteurs)}</div>
                    <div class="metric-label">Acteurs</div>
                    <div class="progress mt-2" style="height: 5px;">
                        <div class="progress-bar progress-bar-animated" style="width: 100%;"></div>
                    </div>
                </div>
            </div>
            <div class="col-md-3 col-sm-6">
                <div class="metric-card position-relative">
                    <i class="bi bi-diagram-3 metric-icon"></i>
                    <div class="metric-value">{len(relations)}</div>
                    <div class="metric-label">Relations</div>
                    <div class="progress mt-2" style="height: 5px;">
                        <div class="progress-bar progress-bar-animated bg-success" style="width: {min(len(relations) / len(acteurs) * 100, 100):.0f}%;"></div>
                    </div>
                </div>
            </div>
            <div class="col-md-3 col-sm-6">
                <div class="metric-card position-relative">
                    <i class="bi bi-diagram-2 metric-icon"></i>
                    <div class="metric-value">{len(analyse.communautes)}</div>
                    <div class="metric-label">Communautés</div>
                    <div class="progress mt-2" style="height: 5px;">
                        <div class="progress-bar progress-bar-animated bg-warning" style="width: {len(analyse.communautes) * 20}%;"></div>
                    </div>
                </div>
            </div>
            <div class="col-md-3 col-sm-6">
                <div class="metric-card position-relative">
                    <i class="bi bi-graph-up metric-icon"></i>
                    <div class="metric-value">{analyse.densite:.2f}</div>
                    <div class="metric-label">Densité</div>
                    <div class="progress mt-2" style="height: 5px;">
                        <div class="progress-bar progress-bar-animated bg-info" style="width: {analyse.densite * 100}%;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Statistiques Détaillées -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="chart-container">
                    <h5><i class="bi bi-pie-chart"></i> Distribution par Type</h5>
                    <div id="typeDistChart"></div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="chart-container">
                    <h5><i class="bi bi-bar-chart"></i> Top 10 Acteurs Influents</h5>
                    <div id="influenceChart"></div>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-md-6">
                <div class="chart-container">
                    <h5><i class="bi bi-diagram-3"></i> Types de Relations</h5>
                    <div id="relationsChart"></div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="chart-container">
                    <h5><i class="bi bi-speedometer2"></i> Métriques Réseau</h5>
                    <div id="metricsChart"></div>
                </div>
            </div>
        </div>

        <!-- Visualisations Interactives -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="chart-container">
                    <ul class="nav nav-tabs" role="tablist">
                        <li class="nav-item">
                            <a class="nav-link active" data-bs-toggle="tab" href="#carte-tab">
                                <i class="bi bi-map"></i> Carte Interactive
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" data-bs-toggle="tab" href="#graphe-tab">
                                <i class="bi bi-diagram-3"></i> Graphe de Réseau
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" data-bs-toggle="tab" href="#table-tab">
                                <i class="bi bi-table"></i> Tableau des Acteurs
                            </a>
                        </li>
                    </ul>

                    <div class="tab-content p-3">
                        <div id="carte-tab" class="tab-pane fade show active">
                            <iframe src="{Path(fichier_carte).name}" class="visualization-frame"></iframe>
                        </div>
                        <div id="graphe-tab" class="tab-pane fade">
                            <iframe src="{Path(fichier_graphe).name}" class="visualization-frame"></iframe>
                        </div>
                        <div id="table-tab" class="tab-pane fade">
                            <div class="table-responsive">
                                <table id="acteursTable" class="table table-hover table-striped">
                                    <thead class="table-dark">
                                        <tr>
                                            <th>Nom</th>
                                            <th>Type</th>
                                            <th>Ville</th>
                                            <th>Secteurs</th>
                                            <th>Influence</th>
                                            <th>Centralité</th>
                                        </tr>
                                    </thead>
                                    <tbody id="acteursTableBody">
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="text-center text-muted mt-4">
            <p class="mb-1">
                <i class="bi bi-info-circle"></i>
                Dashboard généré par <strong>EcoCartographe</strong> v1.0.0
            </p>
            <p class="mb-0">
                Powered by Folium, PyVis, Plotly, NetworkX & Ollama
            </p>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>

    <script>
        // Données
        const acteurs = {acteurs_json};
        const relations = {relations_json};
        const stats = {json.dumps(stats)};

        // Couleurs par type
        const typeColors = {{
            'entreprise': '#3498db',
            'startup': '#2ecc71',
            'laboratoire': '#e74c3c',
            'universite': '#9b59b6',
            'cluster': '#f39c12',
            'pole_competitivite': '#c0392b',
            'incubateur': '#1abc9c',
            'accelerateur': '#27ae60',
            'financeur': '#2c3e50',
            'collectivite': '#3498db',
            'association': '#e91e63',
            'autre': '#95a5a6'
        }};

        // Graphique Distribution par Type
        const typeData = Object.entries(stats.par_type).map(([type, count]) => ({{
            type: type,
            count: count,
            color: typeColors[type] || '#95a5a6'
        }}));

        Plotly.newPlot('typeDistChart', [{{
            values: typeData.map(d => d.count),
            labels: typeData.map(d => d.type),
            type: 'pie',
            marker: {{
                colors: typeData.map(d => d.color)
            }},
            textinfo: 'label+percent',
            hovertemplate: '<b>%{{label}}</b><br>Nombre: %{{value}}<br>%{{percent}}<extra></extra>'
        }}], {{
            height: 400,
            showlegend: true,
            legend: {{ orientation: 'h', y: -0.2 }}
        }});

        // Graphique Top Acteurs
        const topActeurs = acteurs
            .sort((a, b) => b.influence - a.influence)
            .slice(0, 10);

        Plotly.newPlot('influenceChart', [{{
            y: topActeurs.map(a => a.nom.substring(0, 25)),
            x: topActeurs.map(a => a.influence),
            type: 'bar',
            orientation: 'h',
            marker: {{
                color: topActeurs.map(a => typeColors[a.type] || '#95a5a6'),
                line: {{ width: 1, color: '#fff' }}
            }},
            hovertemplate: '<b>%{{y}}</b><br>Influence: %{{x:.3f}}<extra></extra>'
        }}], {{
            height: 400,
            margin: {{ l: 150 }},
            xaxis: {{ title: 'Score d\'Influence' }},
            yaxis: {{ title: '' }}
        }});

        // Graphique Types de Relations
        const relData = Object.entries(stats.par_type_relation);
        Plotly.newPlot('relationsChart', [{{
            values: relData.map(([, count]) => count),
            labels: relData.map(([type,]) => type),
            type: 'pie',
            hole: 0.4,
            textinfo: 'label+value',
            hovertemplate: '<b>%{{label}}</b><br>Nombre: %{{value}}<extra></extra>'
        }}], {{
            height: 400,
            showlegend: true,
            legend: {{ orientation: 'h', y: -0.2 }}
        }});

        // Graphique Métriques Réseau
        const metrics = [
            {{ metric: 'Densité', value: stats.densite, max: 1 }},
            {{ metric: 'Clustering', value: stats.clustering, max: 1 }},
            {{ metric: 'Modularité', value: stats.modularite, max: 1 }}
        ];

        Plotly.newPlot('metricsChart', [{{
            x: metrics.map(m => m.metric),
            y: metrics.map(m => m.value),
            type: 'bar',
            marker: {{
                color: metrics.map(m => m.value > 0.5 ? '#10b981' : '#f59e0b'),
                line: {{ width: 1, color: '#fff' }}
            }},
            text: metrics.map(m => m.value.toFixed(3)),
            textposition: 'outside',
            hovertemplate: '<b>%{{x}}</b><br>Valeur: %{{y:.3f}}<extra></extra>'
        }}], {{
            height: 400,
            yaxis: {{ range: [0, 1], title: 'Valeur' }},
            xaxis: {{ title: '' }}
        }});

        // DataTable
        $(document).ready(function() {{
            const table = $('#acteursTable').DataTable({{
                data: acteurs,
                columns: [
                    {{
                        data: 'nom',
                        render: (data) => `<strong>${{data}}</strong>`
                    }},
                    {{
                        data: 'type',
                        render: (data) => {{
                            const color = typeColors[data] || '#95a5a6';
                            return `<span class="badge badge-type" style="background-color: ${{color}}; color: white;">${{data}}</span>`;
                        }}
                    }},
                    {{ data: 'ville' }},
                    {{
                        data: 'secteurs',
                        render: (data) => data.join(', ').substring(0, 50) + (data.join(', ').length > 50 ? '...' : '')
                    }},
                    {{
                        data: 'influence',
                        render: (data) => `<div class="progress" style="height: 20px;">
                            <div class="progress-bar" style="width: ${{data*100}}%;">${{data.toFixed(3)}}</div>
                        </div>`
                    }},
                    {{
                        data: 'centralite',
                        render: (data) => data.toFixed(3)
                    }}
                ],
                pageLength: 25,
                order: [[4, 'desc']],
                language: {{
                    url: '//cdn.datatables.net/plug-ins/1.13.7/i18n/fr-FR.json'
                }}
            }});
        }});

        // Export des données
        function exportData() {{
            const dataStr = JSON.stringify({{ acteurs, relations, stats }}, null, 2);
            const dataBlob = new Blob([dataStr], {{ type: 'application/json' }});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'ecocartographe_data.json';
            link.click();
        }}
    </script>
</body>
</html>
"""

        # Sauvegarder
        chemin = self.output_dir / nom_fichier
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(html)

        return str(chemin)

    def _calculer_statistiques(
        self, acteurs: list[Acteur], relations: list[Relation], analyse: AnalyseReseau
    ) -> dict[str, Any]:
        """Calcule des statistiques pour les graphiques"""

        # Distribution par type
        par_type = {}
        for acteur in acteurs:
            type_str = acteur.type.value
            par_type[type_str] = par_type.get(type_str, 0) + 1

        # Distribution des relations
        par_type_relation = {}
        for relation in relations:
            type_str = relation.type.value
            par_type_relation[type_str] = par_type_relation.get(type_str, 0) + 1

        return {
            "par_type": par_type,
            "par_type_relation": par_type_relation,
            "densite": analyse.densite,
            "clustering": analyse.coefficient_clustering_moyen,
            "modularite": analyse.modularite,
        }

    def _acteurs_to_json(self, acteurs: list[Acteur]) -> str:
        """Convertit les acteurs en JSON pour JavaScript"""
        acteurs_data = []
        for acteur in acteurs:
            acteurs_data.append(
                {
                    "id": acteur.id,
                    "nom": acteur.nom,
                    "type": acteur.type.value,
                    "ville": acteur.adresse.ville if acteur.adresse else "",
                    "secteurs": acteur.secteurs[:3],
                    "influence": acteur.metriques.score_influence,
                    "centralite": acteur.metriques.degre,
                }
            )
        return json.dumps(acteurs_data)

    def _relations_to_json(self, relations: list[Relation]) -> str:
        """Convertit les relations en JSON pour JavaScript"""
        relations_data = []
        for relation in relations:
            relations_data.append(
                {
                    "source": relation.source_id,
                    "target": relation.cible_id,
                    "type": relation.type.value,
                    "force": relation.force,
                }
            )
        return json.dumps(relations_data)
