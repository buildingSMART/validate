import { useEffect, useMemo, useState, useContext } from 'react';

import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Divider from '@mui/material/Divider';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';

import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';

import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableRow from '@mui/material/TableRow';
import TableContainer from '@mui/material/TableContainer';

import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SearchOffOutlinedIcon from '@mui/icons-material/SearchOffOutlined';

import { FETCH_PATH } from './environment';
import { PageContext } from './Page';
import { getCookieValue } from './Cookies';
import SideMenu from './SideMenu';
import ResponsiveAppBar from './ResponsiveAppBar';
import HandleAsyncError from './HandleAsyncError';

function humanize(s) {
    return String(s || '')
        .replace(/__/g, ' / ')
        .replace(/_/g, ' ')
        .replace(/\s+/g, ' ')
        .trim().split(' ').slice(-1)[0];
}

function monoBoxStyle() {
    return {
        fontFamily:
            'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
        fontSize: 13,
        background: 'rgba(0,0,0,0.04)',
        borderRadius: 8,
        padding: '6px 10px',
        display: 'inline-block',
        maxWidth: '100%',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        verticalAlign: 'middle',
    };
}

export default function AllowList() {
    const context = useContext(PageContext);

    const handleAsyncError = HandleAsyncError();

    const [data, setData] = useState(null);
    const [isLoaded, setLoaded] = useState(false);
    const [errorStatus, setErrorStatus] = useState(null);
    const [errorMessage, setErrorMessage] = useState(null);

    const [user, setUser] = useState(null);
    const [isLoggedIn, setLogin] = useState(false);
    const [prTitle, setPrTitle] = useState("")

    // @todo remove duplication
    useEffect(() => {
        fetch(context.sandboxId ? `${FETCH_PATH}/api/sandbox/me/${context.sandboxId}` : `${FETCH_PATH}/api/me`, { credentials: 'include', 'x-csrf-token': getCookieValue('csrftoken') })
            .then(response => response.json())
            .then((data) => {
                if (data["redirect"] !== undefined && data["redirect"] !== null) {
                    if (!window.location.href.endsWith(data.redirect)) {
                        window.location.href = data.redirect;
                    }
                }
                else {
                    setLogin(true);
                    setUser(data["user_data"]);
                    data["sandbox_info"]["pr_title"] && setPrTitle(data["sandbox_info"]["pr_title"]);
                }
            })
    }, []);


    useEffect(() => {
        const url = `${FETCH_PATH}/api/allowlist`;

        fetch(url)
            .then((res) => {
                if (!res.ok) {
                    setErrorStatus(res.status);
                    return res.text().then((t) => Promise.reject(t || res.statusText));
                }
                return res.json();
            })
            .then((json) => {
                setData(json);
                setErrorStatus(null);
                setErrorMessage(null);
                setLoaded(true);
            })
            .catch((e) => {
                setErrorMessage(String(e));
                setLoaded(true);
            })
            .catch(handleAsyncError);
    }, [handleAsyncError]);

    const entries = useMemo(() => data?.entries || [], [data]);

    if (!isLoaded) {
        return (
            <Grid container direction="column" alignItems="center" sx={{ px: 2, py: 3 }}>
                <Paper sx={{ width: '100%', maxWidth: 950, p: 2 }}>
                    <Typography variant="h6">Allowlist</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Loading...
                    </Typography>
                </Paper>
            </Grid>
        );
    }

    if (errorStatus) {
        return (
            <Grid container direction="column" alignItems="center" sx={{ px: 2, py: 3 }}>
                <Paper sx={{ width: '100%', maxWidth: 950, p: 3, textAlign: 'center' }}>
                    <Typography variant="h3" sx={{ mb: 1 }}>
                        {errorStatus}
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                        {errorMessage || 'Something went wrong'}
                    </Typography>
                    <SearchOffOutlinedIcon color="disabled" fontSize="large" />
                </Paper>
            </Grid>
        );
    }

    return (
        <Grid direction="column"
            container
            style={{
                minHeight: '100vh', alignItems: 'stretch',
            }} >
            <ResponsiveAppBar user={isLoggedIn ? user : null} />
            <Grid
                container
                flex={1}
                direction="row"
                style={{
                }}
            >
                {isLoggedIn && <SideMenu />}
                <Grid
                    container
                    flex={1}
                    direction="column"
                    alignItems="center"
                    sx={{
                        px: 2,
                        py: 3,
                        backgroundColor: 'rgb(242 246 248)',
                        minHeight: 'calc(100vh - 120px)',
                        border: context?.sandboxId ? 'solid 12px red' : 'none',
                        borderRadius: 2,
                    }}
                >
                    <Paper sx={{ width: '100%', maxWidth: 950, p: 2 }}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
                            <div>
                                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                                    Allowlist
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Detection patterns to filter validation outcomes against known schema defects.
                                </Typography>
                            </div>
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Chip label={`${entries.length} entr${entries.length === 1 ? 'y' : 'ies'}`} />
                            </Stack>
                        </Stack>

                        <Divider sx={{ my: 2 }} />

                        {entries.length === 0 ? (
                            <Typography variant="body1" color="text.secondary">
                                No allowlist entries found.
                            </Typography>
                        ) : (
                            <Stack spacing={1.5}>
                                {entries.map((entry) => {
                                    const frags = entry.fragments || [];

                                    return (
                                        <>
                                            <Stack spacing={0.5} sx={{ width: '100%' }}>
                                                <Stack
                                                    direction="row"
                                                    spacing={1}
                                                    alignItems="center"
                                                    justifyContent="space-between"
                                                    sx={{ width: '100%' }}
                                                >
                                                    <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
                                                        <Chip size="small" label={`#${entry.id}`} />
                                                        <Typography
                                                            variant="subtitle1"
                                                            sx={{ fontWeight: 700, minWidth: 0 }}
                                                            noWrap
                                                        >
                                                            {entry.description || `Entry ${entry.id}`}
                                                        </Typography>
                                                    </Stack>
                                                </Stack>
                                            </Stack>

                                            <Stack spacing={1.25}>
                                                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                                                    <Table size="small" aria-label={`allowlist-entry-${entry.id}`}>
                                                        <TableBody>
                                                            {frags.map((f) => (
                                                                <TableRow key={`frag-${entry.id}-${f.id}`}>
                                                                    <TableCell sx={{ width: '36%' }}>
                                                                        <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                                                            {humanize(f.column)}
                                                                        </Typography>
                                                                    </TableCell>
                                                                    <TableCell sx={{ width: '20%' }}>
                                                                        <Chip size="small" label={humanize(f.operation)} />
                                                                    </TableCell>
                                                                    <TableCell sx={{ width: '44%' }}>
                                                                        <span style={monoBoxStyle()} title={String(f.right_hand_side ?? '')}>
                                                                            {String(f.right_hand_side ?? '')}
                                                                        </span>
                                                                    </TableCell>
                                                                </TableRow>
                                                            ))}
                                                        </TableBody>
                                                    </Table>
                                                </TableContainer>

                                            </Stack>
                                        </>
                                    );
                                })}
                            </Stack>
                        )}
                    </Paper>
                </Grid>
            </Grid>
        </Grid>
    );
}