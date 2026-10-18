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
% raw recording) that scripts/derive_raw_mat.py reads on its next run. It
% holds whichever of these the file's time objects give:
%
%   t_s     N x 1 double, seconds from the first sample   (a datetime/duration VECTOR,
%                                                          or a timetable's RowTimes)
%   dur_s   scalar double, seconds                         (a SCALAR duration: the sample
%                                                          interval if <= 60 s, else the span)
%   t0      char, the first sample's date/time             (any datetime, scalar or vector)
%   source  char, which variables and classes it came from
%
% A file whose only time object is a scalar datetime (a start time, not an
% axis) gets t0 alone; derive_raw_mat.py then falls back to its count rule
% and reports the start time.
%
% It loads only the time variables (whos first; the data matrix is never
% loaded) and never writes to the raw file. Run from the repository root in
% MATLAB (R2025b is installed):
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
fmt = 'yyyy-MM-dd''T''HH:mm:ss.SSS';
[~, stem] = fileparts(path);
outdir = fullfile('DATA', 'derived', 'time_axes');
if ~exist(outdir, 'dir'); mkdir(outdir); end
out = fullfile(outdir, [stem '_time.mat']);
info = whos('-file', path);
fprintf('%s: %d variable(s):', path, numel(info));
for i = 1:numel(info)
    fprintf(' %s (%s %s)', info(i).name, info(i).class, mat2str(info(i).size));
end
fprintf('\n');
pick = find(ismember({info.class}, {'datetime', 'duration', 'timetable'}));
if isempty(pick)
    fprintf('   no datetime/duration/timetable variable: nothing written\n');
    return
end
S = struct();
src = {};
for i = pick
    v = info(i);
    L = load(path, v.name);          % this variable only
    x = L.(v.name);
    if istimetable(x)
        x = x.Properties.RowTimes;
    end
    src{end + 1} = sprintf('%s (%s %s)', v.name, v.class, mat2str(v.size)); %#ok<AGROW>
    if isdatetime(x)
        S.t0 = char(x(1), fmt);
        if ~isscalar(x)
            if isfield(S, 't_s'); fprintf('   more than one time vector: %s replaces the earlier one\n', v.name); end
            S.t_s = seconds(x(:) - x(1));
        end
    elseif isduration(x)
        if isscalar(x)
            S.dur_s = seconds(x);
        else
            if isfield(S, 't_s'); fprintf('   more than one time vector: %s replaces the earlier one\n', v.name); end
            S.t_s = seconds(x(:) - x(1));
        end
    else
        fprintf('   %s is %s: not exported\n', v.name, class(x));
    end
end
S.source = strjoin(src, '; ');
save(out, '-struct', 'S', '-v7.3');
fprintf('   -> %s:', out);
if isfield(S, 't0'); fprintf(' t0 %s;', S.t0); end
if isfield(S, 'dur_s'); fprintf(' dur_s %g s;', S.dur_s); end
if isfield(S, 't_s')
    dt = diff(S.t_s);
    fprintf(' t_s %d times, span %.6g s, dt min %.6g / median %.6g / max %.6g s', ...
        numel(S.t_s), S.t_s(end), min(dt), median(dt), max(dt));
end
fprintf('\n');
end
