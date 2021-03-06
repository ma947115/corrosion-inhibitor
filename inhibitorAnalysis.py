# Time series analysis of corrosion rate (dataInhibitor)

import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FormatStrFormatter
from sklearn.compose import make_column_transformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVR
from sklearn.utils import shuffle
from sklearn.inspection import permutation_importance

matplotlib.use('Agg')
matplotlib.rcParams['font.family'] = "Times New Roman"
matplotlib.rcParams['axes.linewidth'] = 1.5
target = {'regression': 'corrosion_mm_yr'}

# ----------------------------------------------------------------------------------------------------------------------
# Variables
# ----------------------------------------------------------------------------------------------------------------------
param = dict(test_size=0.25, cv=5, scoring='mse', replicas=10, grid_search=False, compare_models=False)


# ----------------------------------------------------------------------------------------------------------------------
# Implemented Functions
# ----------------------------------------------------------------------------------------------------------------------
def stack_data(df, _set):
    conc = df['concentration_ppm'].unique()
    df2 = pd.DataFrame()
    i = 0
    for c in conc:
        if c == conc[0]:
            df2 = df.loc[df['concentration_ppm'] == c].reset_index(drop=True)
            df2['time_hrs_original'] = df2['time_hrs']
            _min, _max = df2['time_hrs'].min(), df2['time_hrs'].max()
            df2['time_hrs'] = df2['time_hrs'] - _min
            df2['pre_concentration_zero'] = 'Yes'
            df2['pre_concentration_ppm'] = 0
            if _set == 'training':
                df2['initial_corrosion_mm_yr'] = df.loc[0, 'corrosion_mm_yr']
        else:
            df3 = df.loc[df['concentration_ppm'] == c].reset_index(drop=True)
            df3['time_hrs_original'] = df3['time_hrs']
            _min, _max = df3['time_hrs'].min(), df3['time_hrs'].max()
            df3['time_hrs'] = df3['time_hrs'] - _min
            if i == 1:
                df3['pre_concentration_zero'] = 'Yes'
            else:
                df3['pre_concentration_zero'] = 'No'
            df3['pre_concentration_ppm'] = conc[i - 1]
            if _set == 'training':
                df3['initial_corrosion_mm_yr'] = df.loc[0, 'corrosion_mm_yr']
            df2 = pd.concat([df2, df3], ignore_index=True)
        i += 1
    return df2


def read_exp(df, _set):
    df.columns = df.columns.str.replace(', ', '_')
    df.columns = df.columns.str.replace(' ', '_')
    replicas = df['Description'].unique()
    df2 = pd.DataFrame()
    for replica in replicas:
        if replica == replicas[0]:
            df2 = df.loc[df['Description'] == replica].reset_index(drop=True)
            df2 = stack_data(df2, _set)
        else:
            df3 = df.loc[df['Description'] == replica].reset_index(drop=True)
            df3 = stack_data(df3, _set)
            df2 = pd.concat([df2, df3], ignore_index=True)
    return df2


def clean_data(df):
    df = df[df['corrosion_mm_yr'] >= 0.0]
    aux, aux2 = np.log10(df['corrosion_mm_yr']), np.log10(df['initial_corrosion_mm_yr'])
    df = df.drop(['corrosion_mm_yr', 'initial_corrosion_mm_yr'], axis=1)
    df['corrosion_mm_yr'], df['initial_corrosion_mm_yr'] = aux, aux2
    df = df.dropna(axis=0, how='any').reset_index(drop=True)
    df['Lab'] = df['Lab'].str.rstrip()
    df['Type_of_test'] = df['Type_of_test'].str.rstrip()
    df = df.replace({'Type_of_test': {'Sequential Dose': 'sequential_dose',
                                      'Single Dose YP': 'single_dose_YP',
                                      'Single Dose NP': 'single_dose_NP'},
                     'pH': {6: 'Controlled=6'}})
    return df


def read_data(file_name, new):
    if new:
        sheet_names = pd.ExcelFile('{}.xlsx'.format(file_name)).sheet_names
        df = pd.DataFrame()
        n = 0
        for sheet_name in sheet_names:
            if sheet_name == sheet_names[0]:
                df = pd.read_excel('{}.xlsx'.format(file_name), sheet_name=sheet_name)
                df = read_exp(df, 'training')
                df['Experiment'] = n + 1
            else:
                df2 = pd.read_excel('{}.xlsx'.format(file_name), sheet_name=sheet_name)
                df2 = read_exp(df2, 'training')
                df2['Experiment'] = n + 1
                df = pd.concat([df, df2], ignore_index=True)
            n += 1
            print(n)
        df = clean_data(df)
        excel_output(df, _root='', file_name='{}Cleaned'.format(file_name), csv=True)
    else:
        df = pd.read_csv('{}Cleaned.csv'.format(file_name))
        df = df.drop(['Unnamed: 0'], axis=1)
        n = len(df['Experiment'].unique())
    return df, n


def filter_lab(df, lab):
    if lab != 'All':
        df = df[df['Lab'] == lab].reset_index(drop=True)
    return df


def remove_replicas(df):
    df2 = df.copy(deep=True)
    _off_replicas = [(5, 'Test 5'), (5, 'Test 6'), (5, 'Test 7'), (5, 'Test 8'),  # Experiment 5 is out
                     (19, 'SD 43'), (19, 'SD 44'), (19, 'SD 45'), (19, 'SD 46'),  # Experiment 19 is out
                     (22, 'SD 53'), (22, 'SD 54'),  # Experiment 22 is out
                     (25, 'NP 8'), (25, 'NP 9'), (25, 'NP 10'), (25, 'NP 11')]  # Experiment 25 is out
    for replica in _off_replicas:
        df2 = df2.loc[df2['Description'] != replica[1]]
    df2 = df2.reset_index(drop=True)
    return df2, _off_replicas


def representative_replica(df):
    df2 = df.copy(deep=True)
    _off_replicas = [(6, 'Test 10'), (6, 'Test 11'),
                     (7, 'Test 12'), (7, 'Test 14'),
                     (8, 'Test 16'),
                     (9, 'Test 18'),
                     (10, 'Test 19'), (10, 'Test 20'), (10, 'Test 21'), (10, 'Test 23'), (10, 'Test 24'),
                     (10, 'Test 25'), (10, 'Test 26'), (10, 'Test 27'),
                     (11, 'SD 6'),
                     (12, 'SD 7'), (12, 'SD 9'), (12, 'SD 10'),
                     (13, 'SD 11'),
                     (14, 'SD 13'), (14, 'SD 14'), (14, 'SD 15'), (14, 'SD 16'), (14, 'SD 17'), (14, 'SD 18'),
                     (14, 'SD 19'), (14, 'SD 21'), (14, 'SD 22'), (14, 'SD 23'), (14, 'SD 24'), (14, 'SD 25'),
                     (14, 'SD 26'), (14, 'SD 27'), (14, 'SD 28'), (14, 'SD 29'), (14, 'SD 30'),
                     (15, 'SD 31'), (15, 'SD 32'), (15, 'SD 33'),
                     (16, 'SD 36'), (16, 'SD 37'), (16, 'SD 38'),
                     (17, 'SD 39'),
                     (18, 'SD 42'),
                     (20, 'SD 47'), (20, 'SD 49'), (20, 'SD 50'),
                     (21, 'SD 52'),
                     (23, 'NP 2'), (23, 'NP 3'),
                     (24, 'NP 4'), (24, 'NP 5'), (24, 'NP 7'),
                     (26, 'NP 13'), (26, 'NP 14'), (26, 'NP 15'),
                     (27, 'NP 16'), (27, 'NP 18'), (27, 'NP 19'),
                     (28, 'NP 20'), (28, 'NP 21'), (28, 'NP 22'),
                     (29, 'NP 24'), (29, 'NP 25'), (29, 'NP 27'), (29, 'NP 28'), (29, 'NP 29'), (29, 'NP 30'),
                     (29, 'NP 31')]
    for replica in _off_replicas:
        df2 = df2.loc[df2['Description'] != replica[1]]
    df2 = df2.reset_index(drop=True)
    return df2


def update_data(df, remove, lab):
    df2 = filter_lab(df, lab)
    if remove:
        df2 = remove_replicas(df2)
    return df2


def columns_stats(df, _set, _root):
    statistics = pd.DataFrame()
    for column in df.columns:
        if (column != 'time_hrs') and (column != 'time_hrs_original') and \
                (column != 'corrosion_mm_yr') and (column != 'initial_corrosion_mm_yr'):
            if column == df.columns[0]:
                statistics = pd.DataFrame(df[column].value_counts()).reset_index(drop=False)
                statistics.rename(columns={'index': column, column: 'Num_samples'}, inplace=True)
            else:
                temp = pd.DataFrame(df[column].value_counts()).reset_index(drop=False)
                temp.rename(columns={'index': column, column: 'Num_samples'}, inplace=True)
                statistics = pd.concat([statistics, temp], axis=1)
    excel_output(statistics, _root=_root, file_name='columnsStats_{}'.format(_set), csv=False)


def experiments_stats(df, _set, _root):
    statistics = pd.DataFrame(columns=['Experiment', 'num_replica', 'CI concentration (ppm, hrs)', 'Length_hrs',
                                       'Pressure_bar_CO2', 'Temperature_C', 'CI', 'Shear_Pa',
                                       'Brine_Ionic_Strength', 'pH', 'Brine_Type', 'Type_of_test', 'Lab'])
    _experiments = df['Experiment'].unique()
    for _exp in _experiments:
        df2 = df.loc[df['Experiment'] == _exp].reset_index(drop=True)
        df3 = df2.groupby('concentration_ppm')['time_hrs'].max()
        n_replica = len(df2['Description'].unique())
        conc = df2['concentration_ppm'].unique()
        conc_ppm = ''
        for c in conc:
            t = df3.loc[c]
            if c == conc[0]:
                conc_ppm = conc_ppm + '({:.0f}, {:.0f})'.format(c, t)
            else:
                conc_ppm = conc_ppm + ' - ({:.0f}, {:.0f})'.format(c, t)
        statistics = statistics.append({'Experiment': _exp,
                                        'num_replica': n_replica,
                                        'CI concentration (ppm, hrs)': conc_ppm,
                                        'Length_hrs': '~ {:.0f}'.format(df3.sum()),
                                        'Pressure_bar_CO2': df2.loc[0, 'Pressure_bar_CO2'],
                                        'Temperature_C': df2.loc[0, 'Temperature_C'],
                                        'CI': df2.loc[0, 'CI'],
                                        'Shear_Pa': df2.loc[0, 'Shear_Pa'],
                                        'Brine_Ionic_Strength': df2.loc[0, 'Brine_Ionic_Strength'],
                                        'pH': df2.loc[0, 'pH'],
                                        'Brine_Type': df2.loc[0, 'Brine_Type'],
                                        'Type_of_test': df2.loc[0, 'Type_of_test'],
                                        'Lab': df2.loc[0, 'Lab']}, ignore_index=True)
    excel_output(statistics, _root=_root, file_name='experimentsStats_{}'.format(_set), csv=False)


def view_data_exp(df, y_axis_scale, _set, _root):
    _root = '{}/{}{}'.format(_root, _set, y_axis_scale)
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    _experiments = df['Experiment'].unique()
    for _exp in _experiments:
        df2 = df.loc[df['Experiment'] == _exp]
        replicas = df2['Description'].unique()
        fig, ax = plt.subplots(1, figsize=(9, 9))
        _X_plot = pd.Series(dtype='float64')
        n = 1
        for rep in replicas:
            df3 = df2.loc[df['Description'] == rep]
            _X = df3['time_hrs_original']
            _y = 10 ** (df3['corrosion_mm_yr'])
            plt.scatter(_X, _y, label='Replica {}'.format(n))
            if n == 1:
                _X_plot = _X
            n += 1
        if y_axis_scale == 'Log':
            plt.yscale('log')
            # ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
            if _exp == 14:
                ax.set_ylim(0.001, 100)
                # ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
            else:
                ax.set_ylim(0.01, 100)
        # ---------------------------------
        plt.text(0.02, 1.03, 'Experiment {}'.format(_exp),
                 ha='left', va='center', transform=ax.transAxes, fontdict={'color': 'k', 'weight': 'bold', 'size': 21})
        # ---------------------------------
        plt.grid(linewidth=0.5)
        x_axis_max = 10 * (1 + int(np.max(_X_plot) / 10))
        if _exp == 6:
            x_axis_max = 40
        elif _exp == 11 or _exp == 13 or _exp == 17 or _exp == 18 or _exp == 19:
            x_axis_max = 25
        elif _exp == 14:
            x_axis_max = 30
        elif _exp == 16:
            x_axis_max = 15
        x_axis_index = np.linspace(0, x_axis_max, num=6)
        ax.set_xticks(x_axis_index)
        ax.set_xlim(0, x_axis_max)
        ax.set_xticklabels(x_axis_index, fontsize=20)
        ax.xaxis.set_major_formatter(FormatStrFormatter('%.0f'))
        ax.set_xlabel('Time (hr)', fontsize=27)
        plt.yticks(fontsize=20)
        ax.set_ylabel('Corrosion Rate (mm/year)', fontsize=27)
        n_col, leg_fontsize = 1, 20
        if _exp == 10 or _exp == 14:
            n_col, leg_fontsize = 2, 18
        plt.legend(loc='upper right', fontsize=leg_fontsize, ncol=n_col, fancybox=True, shadow=True)
        plt.tight_layout()
        plt.savefig('{}/exp{}.png'.format(_root, _exp))
        plt.close()


def experiments_types(df, y_axis_scale, _experiments, _root):
    _root = '{}/experimentsTypes{}'.format(_root, y_axis_scale)
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    for _e in _experiments:
        df2 = df.loc[df['Experiment'] == _e[0]]
        df3 = df2.loc[df['Description'] == _e[1]]
        fig, ax = plt.subplots(1, figsize=(9, 9))
        _X = df3['time_hrs_original'].to_numpy()
        _y = 10 ** (df3['corrosion_mm_yr'].to_numpy())
        marker_size = [50 + i * 0 for i in _y]
        plt.scatter(_X, _y, s=marker_size, c='black')
        if y_axis_scale == 'Log':
            plt.yscale('log')
            ax.set_ylim(0.01, 100)
            plt.yticks(fontsize=20)
        else:
            if _e[0] == 3:
                y_axis_mas = 40
            elif _e[0] == 20:
                y_axis_mas = 10
            else:
                y_axis_mas = 6
            y_axis_index = np.linspace(0, y_axis_mas, num=6)
            ax.set_yticks(y_axis_index)
            ax.set_ylim(0, y_axis_mas)
            ax.set_yticklabels(y_axis_index, fontsize=20)
            ax.yaxis.set_major_formatter(FormatStrFormatter('%.0f'))
        # ---------------------------------
        plt.text(0.02, 1.03, '{}'.format(_e[2]),
                 ha='left', va='center', transform=ax.transAxes, fontdict={'color': 'k', 'weight': 'bold', 'size': 21})
        # ---------------------------------
        plt.grid(linewidth=0.5)
        x_axis_index = np.linspace(0, 10 * (1 + int(np.max(_X) / 10)), num=6)
        ax.set_xticks(x_axis_index)
        ax.set_xlim(0, 10 * (1 + int(np.max(_X) / 10)))
        ax.set_xticklabels(x_axis_index, fontsize=20)
        ax.xaxis.set_major_formatter(FormatStrFormatter('%.0f'))
        ax.set_xlabel('Time (hr)', fontsize=27)
        ax.set_ylabel('Corrosion Rate (mm/year)', fontsize=27)
        plt.tight_layout()
        plt.savefig('{}/exp{}.png'.format(_root, _e[0]))
        plt.close()


def summary_data(df):
    _root = 'regression/dataSummary'
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    columns_stats(df, 'allReplicas', _root)
    experiments_stats(df, 'allReplicas', _root)
    view_data_exp(df, 'Log', 'allReplicas', _root)
    view_data_exp(df, 'Normal', 'allReplicas', _root)
    experiments_types(df, 'Log', [(3, 'Test 3', 'Sequential dose'),
                                  (20, 'SD 50', 'Single dose with pre-corrosion'),
                                  (27, 'NP 17', 'Single dose without pre-corrosion')], _root)
    experiments_types(df, 'Normal', [(3, 'Test 3', 'Sequential dose'),
                                     (20, 'SD 50', 'Single dose with pre-corrosion'),
                                     (27, 'NP 17', 'Single dose without pre-corrosion')], _root)
    # ---------------------------------
    df2, _temp = remove_replicas(df)
    columns_stats(df2, 'selReplicas', _root)
    experiments_stats(df2, 'selReplicas', _root)
    view_data_exp(df2, 'Log', 'selReplicas', _root)
    view_data_exp(df2, 'Normal', 'selReplicas', _root)


def excel_output(_object, _root, file_name, csv):
    if csv:
        if _root != '':
            _object.to_csv('{}/{}.csv'.format(_root, file_name))
        else:
            _object.to_csv('{}.csv'.format(file_name))
    else:
        if _root != '':
            _object.to_excel('{}/{}.xls'.format(_root, file_name))
        else:
            _object.to_excel('{}.xls'.format(file_name))


# ----------------------------------------------------------------------------------------------------------------------
def select_features(df):
    df = df[['concentration_ppm', 'pre_concentration_zero', 'pre_concentration_ppm', 'time_hrs',
             'Pressure_bar_CO2', 'Temperature_C', 'CI', 'Shear_Pa', 'Brine_Ionic_Strength',
             'pH', 'Brine_Type', 'Type_of_test', 'initial_corrosion_mm_yr', 'Description', 'Experiment',
             'corrosion_mm_yr']]
    return df


def encode_data(df):
    cat_index = ['pre_concentration_zero', 'CI', 'pH', 'Brine_Type', 'Type_of_test']
    num_index = ['Pressure_bar_CO2', 'Temperature_C', 'Shear_Pa', 'Brine_Ionic_Strength']
    ohe = OneHotEncoder(sparse=False, handle_unknown='ignore')
    sc = StandardScaler()
    ct = make_column_transformer((ohe, cat_index), (sc, num_index), remainder='passthrough')
    ct.fit_transform(df)
    df2 = ct.transform(df)
    # ---------------------------------
    names = []
    for cat in cat_index:
        unique = df[cat].value_counts().sort_index()
        for name in unique.index:
            names.append('{}_{}'.format(cat, name))
    for num in num_index:
        names.append(num)
    names.append('concentration_ppm')
    names.append('pre_concentration_ppm')
    names.append('time_hrs')
    names.append('initial_corrosion_mm_yr')
    names.append('Description')
    names.append('Experiment')
    names.append('corrosion_mm_yr')
    # ---------------------------------
    df2 = pd.DataFrame(df2)
    df2.columns = names
    return df2


def split_data_random(df, test_size):
    df = df.copy(deep=True)
    df = shuffle(df)
    head = int((1 - test_size) * len(df))
    tail = len(df) - head
    df_train = df.head(head).reset_index(drop=True)
    df_test = df.tail(tail).reset_index(drop=True)
    return df_train, df_test


def split_xy(df, _shuffle):
    if _shuffle:
        df = shuffle(df)
    df = df.drop(['Description', 'Experiment'], axis=1)
    _X = df.iloc[:, 0:-1].reset_index(drop=True)
    _y = df.iloc[:, -1].to_numpy()
    return _X, _y


def grid_search(model):
    models = []
    hp1 = {'MLP': [(2,), (4,), (6,), (8,), (10,),
                   (2, 2), (4, 4), (6, 6), (8, 8), (10, 10),
                   (2, 2, 2), (4, 4, 4), (6, 6, 6), (8, 8, 8), (10, 10, 10),
                   (2, 2, 2, 2), (4, 4, 4, 4), (6, 6, 6, 6), (8, 8, 8, 8), (10, 10, 10, 10),
                   (2, 2, 2, 2, 2), (4, 4, 4, 4, 4), (6, 6, 6, 6, 6), (8, 8, 8, 8, 8), (10, 10, 10, 10, 10)],
           'SVM': [1, 0.1, 0.01, 0.001, 0.0001],
           'RF': [10, 50, 100, 200, 500],
           'KNN': [1, 2, 3, 4, 5, 6, 7]}
    hp2 = {'MLP': ['constant'],
           'SVM': [1, 5, 10, 100, 1000],
           'RF': [0.6, 0.7, 0.8, 0.9, 1.0],
           'KNN': ['uniform', 'distance']}
    for n in hp1[model]:
        for m in hp2[model]:
            if model == 'MLP':
                models.append(('MLP_{}_{}'.format(n, m), MLPRegressor(max_iter=10000, random_state=5,
                                                                      hidden_layer_sizes=n, learning_rate=m)))
            elif model == 'SVM':
                models.append(('SVM_{}_{}'.format(n, m), SVR(gamma=n, C=m)))
            elif model == 'RF':
                models.append(('RF_{}_{}'.format(n, m), RandomForestRegressor(random_state=5,
                                                                              n_estimators=n, max_features=m)))
            elif model == 'KNN':
                models.append(('KNN_{}_{}'.format(n, m), KNeighborsRegressor(n_neighbors=n, weights=m)))
    return models


def compare_models(df, models, _param):
    scoring, cv, replicas = 'neg_mean_squared_error', _param['cv'], _param['replicas']
    if _param['scoring'] == 'r2':
        scoring = 'r2'
    # ---------------------------------
    results = pd.DataFrame()
    for i in range(replicas):
        _X_train, _y_train = split_xy(df, True)
        temp = []
        for name, model in models:
            print(name)
            cv_results = cross_val_score(model, _X_train, _y_train, cv=cv, scoring=scoring)
            cv_results = np.mean(cv_results)
            temp.append(cv_results)
        if i == 0:
            results = pd.DataFrame(temp)
        else:
            results = pd.concat([results, pd.DataFrame(temp)], axis=1, ignore_index=True)
    results['mean'] = results.mean(axis=1)
    results['std'] = results.std(axis=1)
    # ---------------------------------
    _names, _models = [], []
    for name, model in models:
        _names.append(name)
        _models.append(model)
    results['name'] = pd.Series(_names)
    results['model'] = pd.Series(_models)
    # ---------------------------------
    id_best = results['mean'].idxmax()
    _best = results.loc[id_best, 'model']
    return results, _best


def prediction(df, estimator, _param):
    test_size, replicas = _param['test_size'], _param['replicas']
    errors = pd.DataFrame()
    for i in range(replicas):
        df_training, df_testing = split_data_random(df, test_size)
        _X_train, _y_train = split_xy(df_training, True)
        estimator.fit(_X_train, _y_train)
        _X_test, _y_test = split_xy(df_testing, True)
        _y_pred = estimator.predict(_X_test)
        errors.loc[i, 'r2'] = r2_score(_y_test, _y_pred)
        errors.loc[i, 'mse'] = mean_squared_error(_y_test, _y_pred)
        errors.loc[i, 'mae'] = mean_absolute_error(_y_test, _y_pred)
        errors.loc[i, 'rmse'] = np.sqrt(mean_squared_error(_y_test, _y_pred))
    _scores = [('R2', np.mean(errors['r2']), np.std(errors['r2'])),
               ('MSE', np.mean(errors['mse']), np.std(errors['mse'])),
               ('MAE', np.mean(errors['mae']), np.std(errors['mae'])),
               ('RMSE', np.mean(errors['rmse']), np.std(errors['rmse']))]
    return _scores


def split_data_exp(df, _seat_out):
    df_train = df.copy(deep=True)
    df_test = pd.DataFrame()
    for _exp in _seat_out:
        df_train = df_train.loc[df_train['Experiment'] != _exp]
        df_test = pd.concat([df_test, df.loc[df['Experiment'] == _exp]], ignore_index=True)
    df_test = representative_replica(df_test)
    return df_train, df_test


def production(df, y_series):
    df_prod = df.copy(deep=True)
    replicas = [i for i in df_prod['initial_corrosion_mm_yr'].unique()]
    df_prod = df_prod.loc[df_prod['initial_corrosion_mm_yr'] == replicas[0]]
    _y_prod = y_series[:len(df_prod)]
    return df_prod, _y_prod


def sensitivity(df_original, df, _experiment):
    df_time = df_original.copy(deep=True)
    df_time = df_time.loc[df_time['Experiment'] == _experiment].reset_index(drop=True)
    replicas_time = df_time['initial_corrosion_mm_yr'].unique()
    df_time = df_time.loc[df_time['initial_corrosion_mm_yr'] == replicas_time[0]]
    time_hrs_sens = df_time['time_hrs_original']
    # ---------------------------------
    replicas = df['initial_corrosion_mm_yr'].unique()
    df = df.loc[df['initial_corrosion_mm_yr'] == replicas[0]]
    return df, time_hrs_sens


# ----------------------------------------------------------------------------------------------------------------------
def smooth(y_array, window):
    if window != 0:
        y_smoothed = pd.Series(y_array).rolling(window, center=False).mean().shift(-window).to_numpy()
    else:
        y_smoothed = y_array
    return y_smoothed


def compare_models_plot(df):
    _root = 'regression/gridSearchModels'
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    for model_name in ['MLP', 'SVM', 'RF', 'KNN']:
        x_axis_index = [i + 1 for i in np.arange(len(df))]
        _y = [-i for i in df['{}_mean'.format(model_name)]]
        _y_err = df['{}_std'.format(model_name)].tolist()
        bar_width = 0.45
        colors = {'MLP': 'mistyrose', 'SVM': 'cornsilk', 'RF': 'lightgray', 'KNN': 'lightcyan'}
        fig, ax = plt.subplots(1, figsize=(12, 9))
        ax.bar(x_axis_index, _y, width=bar_width, color=colors[model_name], edgecolor='black', zorder=3,
               yerr=_y_err, capsize=5, align='center', ecolor='black', alpha=0.5, label=model_name)
        # ---------------------------------
        letter = {'MLP': 'A', 'RF': 'B', 'KNN': 'C', 'SVM': 'D'}
        plt.text(0.02, 0.98, '{}'.format(letter[model_name]),
                 ha='left', va='top', transform=ax.transAxes,
                 fontdict={'color': 'k', 'weight': 'bold', 'size': 50})
        # ---------------------------------
        ax.grid(axis='y', linewidth=0.35, zorder=0)
        ax.set_xticks(x_axis_index)
        ax.set_xticklabels(x_axis_index, fontsize=20, rotation=45)
        ax.set_xlabel('Grid serach combination', fontsize=30)
        y_axis_max = {'MLP': [0.7, 0.1], 'SVM': [0.6, 0.1], 'RF': [0.3, 0.05], 'KNN': [0.35, 0.05]}
        y_axis_index = np.arange(0, y_axis_max[model_name][0], y_axis_max[model_name][1])
        ax.set_yticks(y_axis_index)
        ax.set_yticklabels(['{:.2f}'.format(i) for i in y_axis_index], fontsize=20)
        ax.set_ylabel('MSE', fontsize=30)
        plt.legend(loc='upper right', fontsize=20, fancybox=True, shadow=True)
        plt.tight_layout()
        plt.savefig('{}/{}.png'.format(_root, model_name))
        plt.close()


def compare_models_box_plot(df, _param):
    _root = 'regression/gridSearchModels'
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    cv, replicas = _param['cv'], _param['replicas']
    # ---------------------------------
    x_axis_labels = [name for name in df['name']]
    df = df.drop(['name', 'mean', 'std', 'model'], axis=1)
    df = df.transform(lambda x: -x)
    _y_matrix = df.values.tolist()
    fig, ax = plt.subplots(1, figsize=(12, 9))
    plt.boxplot(_y_matrix, labels=x_axis_labels, sym='',
                medianprops=dict(color='lightgrey', linewidth=1.0),
                meanprops=dict(linestyle='-', color='black', linewidth=1.5), meanline=True, showmeans=True)
    # ---------------------------------
    info = '{}-fold cross validation analysis \n{} replications per algorithm'.format(cv, replicas)
    plt.text(0.03, 0.96, info,
             ha='left', va='top', transform=ax.transAxes,
             fontdict={'color': 'k', 'size': 18},
             bbox={'boxstyle': 'round', 'fc': 'snow', 'ec': 'gray', 'pad': 0.5})
    # ---------------------------------
    ax.grid(axis='y', linewidth=0.35, zorder=0)
    x_axis_index = [i + 1 for i in np.arange(len(x_axis_labels))]
    ax.set_xticks(x_axis_index)
    ax.set_xticklabels(x_axis_labels, fontsize=30)
    y_axis_index = np.arange(0, 0.06, 0.01)
    ax.set_yticks(y_axis_index)
    ax.set_yticklabels(['{:.2f}'.format(i) for i in y_axis_index], fontsize=20)
    ax.set_ylabel('Mean Squared Error (MSE)', fontsize=28)
    # plt.tight_layout()
    plt.savefig('{}/comparison.png'.format(_root))
    plt.close()


def correlation_plot(df):
    _root = 'regression/bestModelPerformance'
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    corr = df.corr()
    plt.subplots(figsize=(12, 12))
    sns.heatmap(corr, vmin=-1, vmax=1, center=0, cmap='coolwarm', square=True)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.tight_layout()
    plt.savefig('{}/corrMatrix.png'.format(_root))
    plt.close()
    excel_output(pd.DataFrame(corr), _root, file_name='correlation', csv=False)
    # ---------------------------------
    return corr


def importance_plot(df, estimator, _x, _y):
    _root = 'regression/bestModelPerformance'
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    names = df.columns
    imp = estimator.feature_importances_
    indices = np.argsort(imp)
    fig, ax = plt.subplots(1, figsize=(12, 9))
    plt.barh(range(len(indices)), imp[indices], color='black', align='center')
    x_axis_index = np.arange(0, 0.6, 0.1)
    ax.set_xticks(x_axis_index)
    ax.set_xticklabels(x_axis_index, fontsize=20)
    ax.set_xticklabels(['{:.2f}'.format(i) for i in x_axis_index], fontsize=20)
    ax.set_xlabel('Relative Importance', fontsize=30)
    plt.yticks(range(len(indices)), [names[i] for i in indices], fontsize=14)
    plt.tight_layout()
    plt.savefig('{}/featuresImp.png'.format(_root))
    plt.close()
    excel_output(pd.DataFrame(imp), _root, file_name='rf_feature_imp', csv=False)
    # ---------------------------------
    permute_imp_results = permutation_importance(estimator, _x, _y, scoring='neg_mean_squared_error')
    permute_imp = permute_imp_results.importances_mean
    excel_output(pd.DataFrame(permute_imp), _root, file_name='permutation_imp', csv=False)
    return imp, permute_imp


def parity_plot(_y_test, _y_pred, _scores):
    _root = 'regression/bestModelPerformance'
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    info = '{} = {:.3f} +/- {:.3f}\n{} = {:.3f} +/- {:.3f}\n{} = {:.3f} +/- {:.3f}\n{} = {:.3f} +/- {:.3f}'. \
        format(_scores[0][0], _scores[0][1], _scores[0][2],
               _scores[1][0], _scores[1][1], _scores[1][2],
               _scores[2][0], _scores[2][1], _scores[2][2],
               _scores[3][0], _scores[3][1], _scores[3][2])
    # ---------------------------------
    fig, ax = plt.subplots(1, figsize=(9, 9))
    _y_test = 10 ** _y_test
    _y_pred = 10 ** _y_pred
    plt.scatter(_y_pred, _y_test, c='black', label='Testing set')
    a, b = min(_y_test.min(), _y_pred.min()), max(_y_test.max(), _y_pred.max())
    plt.plot([a, b], [a, b], '-', c='goldenrod', linewidth=7.0, label='y = x')
    # ---------------------------------
    plt.text(0.03, 0.96, info,
             ha='left', va='top', transform=ax.transAxes,
             fontdict={'color': 'k', 'size': 18},
             bbox={'boxstyle': 'round', 'fc': 'snow', 'ec': 'gray', 'pad': 0.5})
    # ---------------------------------
    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18)
    ax.set_xlim(0.01, 100)
    ax.set_ylim(0.01, 100)
    plt.xscale('log')
    plt.yscale('log')
    plt.xlabel('Corrosion rate (mm/year) - Predicted', fontsize=25)
    plt.ylabel('Corrosion rate (mm/year) - True', fontsize=25)
    plt.legend(loc='upper right', fontsize=18, fancybox=True, shadow=True)
    plt.tight_layout()
    plt.savefig('{}/parityPlot.png'.format(_root))
    plt.close()
    # ---------------------------------
    df = pd.DataFrame(columns=['True_value', 'Predicted_value'])
    df['True_value'] = _y_test
    df['Predicted_value'] = _y_pred
    excel_output(df, _root, file_name='parityPlotData', csv=False)


def production_plot(df_all, df_selected, _y_prod, folder_name, y_axis_scale, _exp, _seat_out):
    _root = 'regression/postProcessing/{}{}'.format(folder_name, y_axis_scale)
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    fig, ax = plt.subplots(1, figsize=(10, 9))
    # ---------------------------------
    df2 = df_all.copy(deep=True)
    df2 = df2.loc[df2['Experiment'] == _exp]
    replicas = df2['Description'].unique()
    n = 1
    for rep in replicas:
        df3 = df2.loc[df_all['Description'] == rep]
        _X = df3['time_hrs_original']
        _y = 10 ** (df3['corrosion_mm_yr'])
        _color, _zorder = 'gray', 0
        if (_exp, rep) not in off_replicas and folder_name != 'testingTheModel':
            _color, _zorder = 'lightskyblue', 5
        plt.scatter(_X, _y, c=_color, label='Replica {}'.format(n), zorder=_zorder)
        n += 1
    # ---------------------------------
    df2 = df_selected.copy(deep=True)
    df2 = representative_replica(df2)
    df2 = df2.loc[df2['Experiment'] == _exp]
    _X_prod = df2['time_hrs_original']
    plt.scatter(_X_prod, 10 ** _y_prod, c='darkred', marker='^', s=[75], label='Prediction', zorder=7)
    # ---------------------------------
    if y_axis_scale == 'Log':
        plt.yscale('log')
        # ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        if _exp == 14:
            ax.set_ylim(0.001, 100)
            # ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        else:
            ax.set_ylim(0.01, 100)
    # ---------------------------------
    # plt.text(0.02, 1.03, 'Experiment {}'.format(_exp),
    #          ha='left', va='center', transform=ax.transAxes, fontdict={'color': 'k', 'weight': 'bold', 'size': 21})
    # ---------------------------------
    _info = [i for i in _seat_out]
    # if len(_seat_out) > 1:
    #     plt.text(0.4, 1.03,
    #              '(Testing Exps.: {}, {}, {}, {})'.format(_info[0], _info[1], _info[2], _info[3]),
    #              ha='left', va='center',
    #              transform=ax.transAxes, fontdict={'color': 'k', 'weight': 'bold', 'size': 17})
    # ---------------------------------
    plt.grid(linewidth=0.5)
    x_axis_max = 10 * (1 + int(np.max(_X_prod) / 10))
    if _exp == 6:
        x_axis_max = 40
    elif _exp == 11 or _exp == 13 or _exp == 17 or _exp == 18 or _exp == 19:
        x_axis_max = 25
    elif _exp == 14:
        x_axis_max = 30
    elif _exp == 16:
        x_axis_max = 15
    x_axis_index = np.linspace(0, x_axis_max, num=6)
    ax.set_xticks(x_axis_index)
    ax.set_xlim(0, x_axis_max)
    ax.set_xticklabels(x_axis_index, fontsize=30)
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.0f'))
    ax.set_xlabel('Time (hr)', fontsize=40, labelpad=20)
    plt.yticks(fontsize=30)
    ax.set_ylabel('Corrosion rate (mm/yr)', fontsize=40, labelpad=25)
    n_col, legend_font_size = 1, 25
    if _exp == 10 or _exp == 14 or _exp == 29:
        n_col = 2
    if _exp == 14:
        legend_font_size = 18
    leg = plt.legend(loc='upper right', fontsize=legend_font_size, ncol=n_col, fancybox=True, shadow=True)
    for handle, text in zip(leg.legendHandles, leg.get_texts()):
        text.set_color(handle.get_facecolor()[0])
    plt.tight_layout()
    plt.savefig('{}/{} exp{}.png'.format(_root, _info, _exp))
    plt.close()


def sensitivity_plot(df, _exp, y_axis_scale, _feature):
    _root = 'regression/sensitivityAnalysis/exp{}{}'.format(_exp, y_axis_scale)
    if not os.path.exists(_root):
        os.makedirs(_root)
    # ---------------------------------
    fig, ax = plt.subplots(1, figsize=(10, 9))
    # ---------------------------------
    _color = ['black', 'blue', 'green', 'darkorange', 'red']
    _marker = ['o', 'x', '^', 's', 'D']
    _X = df['time_hrs']
    i = 0
    for column in df.columns:
        if column == 'time_hrs':
            continue
        _y = 10 ** (df[column])
        plt.scatter(_X, _y, c=_color[i], marker=_marker[i], s=[75], label='{}'.format(column))
        i += 1
    if y_axis_scale == 'Log':
        plt.yscale('log')
        # ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        if _exp == 14:
            ax.set_ylim(0.001, 100)
            # ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        else:
            ax.set_ylim(0.01, 100)
    # ---------------------------------
    # plt.text(0.04, 0.95, '{}'.format(_feature),
    #          ha='left', va='center', transform=ax.transAxes, fontdict={'color': 'k', 'weight': 'bold', 'size': 25})
    # ---------------------------------
    plt.grid(linewidth=0.5)
    x_axis_max = 10 * (1 + int(np.max(_X) / 10))
    if _exp == 6:
        x_axis_max = 40
    elif _exp == 11 or _exp == 13 or _exp == 17 or _exp == 18 or _exp == 19:
        x_axis_max = 25
    elif _exp == 14:
        x_axis_max = 30
    elif _exp == 16:
        x_axis_max = 15
    x_axis_index = np.linspace(0, x_axis_max, num=6)
    ax.set_xticks(x_axis_index)
    ax.set_xlim(0, x_axis_max)
    ax.set_xticklabels(x_axis_index, fontsize=30)
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.0f'))
    ax.set_xlabel('Time (hr)', fontsize=40, labelpad=20)
    plt.yticks(fontsize=30)
    ax.set_ylabel('Corrosion rate (mm/yr)', fontsize=40, labelpad=25)
    legend_font_size = 23
    plt.legend(loc='upper right', fontsize=legend_font_size, ncol=1, fancybox=True, shadow=True)
    plt.tight_layout()
    plt.savefig('{}/{}.png'.format(_root, _feature))
    plt.close()
    excel_output(df, _root, file_name='{}'.format(_feature), csv=False)


# --------------------------------------------------------------------------------------------------------------------
# BEGIN
# --------------------------------------------------------------------------------------------------------------------

# reading data
dataAll, n_exp = read_data('dataInhibitor', new=False)

# data summary (one-time output)
# summary_data(df=dataAll)

# --------------------------------------------------------------------------------------------------------------------
# REGRESSION PROBLEM
# --------------------------------------------------------------------------------------------------------------------

# # pre-processing data
dataSelected, off_replicas = remove_replicas(dataAll)
inhibitor = select_features(dataSelected)
# correlation = correlation_plot(inhibitor)
inhibitor = encode_data(inhibitor)
#
# grid-search to find the best model of each algorithm (one-time output)
if param['grid_search']:
    root = 'regression/gridSearchModels'
    if not os.path.exists(root):
        os.makedirs(root)
    # ---------------------------------
    best_models = {}
    df_scores = pd.DataFrame()
    for algorithm in ['MLP', 'SVM', 'RF', 'KNN']:
        print(algorithm)
        algorithms = grid_search(algorithm)
        scores, best = compare_models(inhibitor, algorithms, param)
        best_models[algorithm] = best
        df_scores['{}_mean'.format(algorithm)], df_scores['{}_std'.format(algorithm)] = scores['mean'], scores['std']
        printOut = pd.DataFrame(algorithms)
        printOut['mean'], printOut['std'] = [-x for x in scores['mean']], scores['std']
        excel_output(printOut, root, file_name='{}'.format(algorithm), csv=False)
    compare_models_plot(df_scores)
    models_reg = [('MLP', best_models['MLP']),
                  ('SVM', best_models['SVM']),
                  ('RF', best_models['RF']),
                  ('KNN', best_models['KNN'])]
else:
    models_reg = [('MLP', MLPRegressor(hidden_layer_sizes=(8, 8, 8, 8), max_iter=10000)),
                  ('SVM', SVR(C=1000, gamma=1)),
                  ('RF', RandomForestRegressor(max_features=0.7, n_estimators=500, random_state=5)),
                  ('KNN', KNeighborsRegressor(n_neighbors=3, weights='distance'))]

# comparing different models
_best_reg = models_reg[2][1]
if param['compare_models']:
    scores_reg, _best_reg = compare_models(inhibitor, models_reg, param)
    compare_models_box_plot(scores_reg, param)
    excel_output(scores_reg, 'regression/gridSearchModels', file_name='comparison', csv=False)
best_reg = _best_reg

# # features importance
# X, y = split_xy(inhibitor, True)
# best_reg.fit(X, y)
# feature_importance, permute_importance = importance_plot(inhibitor, best_reg)
#
# # parity plot
# training_reg, testing_reg = split_data_random(inhibitor, param['test_size'])
# X_train, y_train = split_xy(training_reg, True)
# best_reg.fit(X_train, y_train)
# X_test, y_test = split_xy(testing_reg, True)
# y_pred = best_reg.predict(X_test)
# scores_pred = prediction(inhibitor, best_reg, param)
# parity_plot(y_test, y_pred, scores_pred)
# excel_output(X_train, 'regression/bestModelPerformance', file_name='trainFeatureMatrixNorm', csv=False)

# # comparing replicas when 1 experiment is out each time
# experiments = [int(i) for i in inhibitor['Experiment'].unique()]
# for exp in experiments:
#     print(exp)
#     seatOut = np.asarray([exp])
#     training_comp, testing_comp = split_data_exp(inhibitor, seatOut)
#     X_train, y_train = split_xy(training_comp, True)
#     X_test, y_test = split_xy(testing_comp, False)
#     best_reg.fit(X_train, y_train)
#     X_prod, y_prod = production(X_test, y_test)
#     y_pred = best_reg.predict(X_prod)
#     production_plot(dataAll, dataSelected, y_pred, 'compareReplicas', 'Log', exp, seatOut)
#     production_plot(dataAll, dataSelected, y_pred, 'compareReplicas', 'Normal', exp, seatOut)

# testing the model when 4 experiment (25% of the data) are out
# seatOuts = [[2, 17, 27, 29], [4, 7, 14, 24], [4, 8, 10, 12], [10, 23, 24, 27], [12, 14, 17, 20], [11, 12, 13, 17],
#             [1, 10, 12, 28], [2, 6, 13, 18], [9, 11, 13, 20], [11, 13, 15, 23], [1, 13, 15, 29], [10, 15, 18, 20],
#             [1, 8, 15, 28], [12, 20, 23, 29]]
# experiments = inhibitor['Experiment'].unique()
# seatOuts = [[int(i) for i in np.random.choice(a=experiments, size=4, replace=False)], [12, 20, 23, 29]]
# for seatOut in seatOuts:
#     training_test, testing_test = split_data_exp(inhibitor, seatOut)
#     X_train, y_train = split_xy(training_test, True)
#     best_reg.fit(X_train, y_train)
#     for exp in seatOut:
#         testing_temp = testing_test.loc[testing_test['Experiment'] == exp].reset_index(drop=True)
#         X_test, y_test = split_xy(testing_temp, False)
#         X_prod, y_prod = production(X_test, y_test)
#         y_pred = best_reg.predict(X_prod)
#         production_plot(dataAll, dataSelected, y_pred, 'testingTheModel', 'Log', exp, seatOut)
#         production_plot(dataAll, dataSelected, y_pred, 'testingTheModel', 'Normal', exp, seatOut)

# sensitivity analysis
experiments = [11]
# experiments = [int(i) for i in inhibitor['Experiment'].unique()]
# experiment = [i for i in np.random.choice(a=experiments, size=1, replace=False)]
features_reg = {'CI': [['CORR12148SP', 'EC1612A'], [0.0, 0.0], 'Corrosion inhibitor', 'CI', ''],
                'pH': [['Controlled=6', 'Uncontrolled'], [0.0, 0.0], 'pH', 'pH', ''],
                'Brine_Type': [['TH', 'Galapagos'], [0.0, 0.0], 'Brine type', 'type', ''],
                'Pressure_bar_CO2': [[0.5, 5, 12], [4.51, 3.15], 'CO2 partial pressure', 'P_CO2', 'bar'],
                'Temperature_C': [[90, 110, 132], [106.69, 19.34], 'Temperature', 'T', 'C'],
                'Shear_Pa': [[20, 100, 300], [32.85, 56.01], 'Shear stress', 'P', 'Pa'],  # mean, sdv = 32.85, 56.01
                'Brine_Ionic_Strength': [[0.5, 1.5, 2.5], [0.87, 0.62], 'Brine ionic strength', 'S', ''],
                'concentration_ppm': [[100, 200, 300], [190.21, 131.99],
                                      'Inhibitor concentration', 'C', 'ppm']}
for experiment in experiments:
    print(experiment)
    training_sens, testing_sens = split_data_exp(inhibitor, [experiment])
    X_train, y_train = split_xy(inhibitor, True)
    best_reg.fit(X_train, y_train)
    testing_sens, time_sens = sensitivity(dataSelected, testing_sens, experiment)
    for key in features_reg:
        print(key)
        first = True
        sensitivity_df = pd.DataFrame(index=range(len(testing_sens)))
        sensitivity_df['time_hrs'] = time_sens
        for value in features_reg[key][0]:
            testing_temp = testing_sens.copy(deep=True)
            if first and key in ['CI', 'pH', 'Brine_Type']:
                testing_temp['{}_{}'.format(key, features_reg[key][0][0])] = [1.0] * len(testing_sens)
                testing_temp['{}_{}'.format(key, features_reg[key][0][1])] = [0.0] * len(testing_sens)
                first = False
            elif key in ['CI', 'pH', 'Brine_Type']:
                testing_temp['{}_{}'.format(key, features_reg[key][0][0])] = [0.0] * len(testing_sens)
                testing_temp['{}_{}'.format(key, features_reg[key][0][1])] = [1.0] * len(testing_sens)
            else:
                key_mean, key_std = np.mean(dataSelected[key]), np.std(dataSelected[key])
                zero_norm = (0 - key_mean) / float(key_std)
                value_norm = (value - key_mean) / float(key_std)
                if key != 'concentration_ppm':
                    testing_temp[key] = [value_norm] * len(testing_sens)
                else:
                    for v in range(len(testing_temp)):
                        if testing_temp.loc[v, 'concentration_ppm'] != 0:
                            testing_temp.loc[v, 'concentration_ppm'] = value
            X_sens = testing_temp.drop(['Description', 'Experiment', 'corrosion_mm_yr'], axis=1)
            y_sens = best_reg.predict(X_sens)
            value = 130 if value == 132 else value
            sensitivity_df['{} = {} {}'.format(features_reg[key][3], value, features_reg[key][4])] = y_sens
        sensitivity_plot(sensitivity_df, experiment, 'Log', features_reg[key][2])
        sensitivity_plot(sensitivity_df, experiment, 'Normal', features_reg[key][2])

# ----------------------------------------------------------------------------------------------------------------------
# The End
# ----------------------------------------------------------------------------------------------------------------------
print('DONE!')
