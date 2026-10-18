function export_mat_time(varargin)
%EXPORT_MAT_TIME  Write each raw file's MATLAB time object as plain seconds.
%
%   export_mat_time('DATA/raw/CO.mat', 'DATA/raw/LM.mat', ...)
%   export_mat_time()   % the six October 2026 files under DATA/raw
%
% Why (datasets-derive, 2026-10-18). CO, LM, SH, SO, F2B and
% L_R_Aug_26_PD_raw each carry their time axis as a MATLAB object (datetime,
% duration or timetable) that Python's scipy reads only as an undecodable
% MatlabOpaque. This writes DATA/derived/time_axes/<stem>_time.mat (-v7.3;
% not beside the raw file, where Settings › Datasets would list it as a
% raw recording) that scripts/derive_raw_mat.py reads on its next run:
%
%   t_s     N x 1 double, seconds from the first sample   (a vector time object)
%   dur_s   scalar double, seconds                         (a scalar duration)
%   t0      char, the first sample's date/time when the object is a datetime
%   source  char, which variable and class it came from
%
% It loads only the small variables (whos first; the data matrix is never
% loaded). Run from the repository root in MATLAB (R2025b is installed):
%
%   cd C:\Users\mmebr\Documents\CNN
%   addpath scripts; export_mat_time()
%   python scripts/derive_raw_mat.py CO LM SH SO F2B L_R_Aug_26_PD_raw --dry-run
%
% Untested here: written in a worktree with no MATLAB run (the manager runs it).

if nargin == 0
    names = {'CO', 'LM', 'SH', 'SO', 'F2B', 'L_R_Aug_26_PD_raw'};
    varargin = cellfun(@(n) fullfile('DATA', 'raw', [n '.mat']), names, 'UniformOutput', false);
end
for k = 1:numel(varargin)
    export_one(varargin{k});
end
end

function export_one(path)
[~, stem] = fileparts(path);
outdir = fullfile('DATA', 'derived', 'time_axes');
if ~exist(outdir, 'dir'); mkdir(outdir); end
out = fullfile(outdir, [stem '_time.mat']);
info = whos('-file', path);
classes = {info.class};
pick = find(ismember(classes, {'datetime', 'duration', 'timetable', 'calendarDuration'}));
fprintf('%s: %d variable(s):', path, numel(info));
for i = 1:numel(info)
    fprintf(' %s (%s %s)', info(i).name, info(i).class, mat2str(info(i).size));
end
fprintf('\n');
if isempty(pick)
    fprintf('   no datetime/duration/timetable variable: nothing written\n');
    return
end
if numel(pick) > 1
    fprintf('   %d time objects (%s): using the first; check the others by hand\n', numel(pick), strjoin({info(pick).name}, ', '));
end
v = info(pick(1));
S = load(path, v.name);
x = S.(v.name);
source = sprintf('%s (%s %s)', v.name, v.class, mat2str(v.size));
t0 = '';
switch v.class
    case 'timetable'
        x = x.Properties.RowTimes;
end
if isdatetime(x)
    t_s = seconds(x(:) - x(1));
    t0 = char(string(x(1), 'yyyy-MM-dd''T''HH:mm:ss.SSS'));
elseif isduration(x)
    if isscalar(x)
        dur_s = seconds(x);
        save(out, 'dur_s', 'source', '-v7.3');
        fprintf('   scalar duration %g s -> %s (dur_s)\n', dur_s, out);
        return
    end
    t_s = seconds(x(:) - x(1));
else
    fprintf('   %s is %s: not exported\n', v.name, class(x));
    return
end
save(out, 't_s', 't0', 'source', '-v7.3');
dt = diff(t_s);
fprintf('   %d times, span %.6g s, dt min %.6g / median %.6g / max %.6g s -> %s\n', ...
    numel(t_s), t_s(end), min(dt), median(dt), max(dt), out);
end
