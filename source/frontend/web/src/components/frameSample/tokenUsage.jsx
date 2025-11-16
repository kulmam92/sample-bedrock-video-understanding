import React from 'react';
import { FetchPost } from "../../resources/data-provider";
import { 
    Box, 
    ColumnLayout, 
    Container, 
    Header, 
    Spinner, 
    Alert,
    SpaceBetween,
    Badge,
    ExpandableSection,
    Popover,
    Button
} from '@cloudscape-design/components';
import REGIONAL_PRICING from '../../resources/pricing-config.json';
import './tokenUsage.css';

class TokenUsage extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            loading: true,
            error: null,
            usageData: null,
        };
    }

    async componentDidMount() {
        await this.fetchTokenUsage();
    }

    async componentDidUpdate(prevProps) {
        if (prevProps.taskId !== this.props.taskId) {
            await this.fetchTokenUsage();
        }
    }

    async fetchTokenUsage() {
        this.setState({ loading: true, error: null });
        
        try {
            const data = await FetchPost(
                "/extraction/video/get-token-and-cost",
                { task_id: this.props.taskId },
                "ExtrService"
            );
            console.log(data);
            if (data.statusCode !== 200) {
                this.setState({ 
                    loading: false, 
                    error: data.body?.error || "Failed to fetch token usage data" 
                });
            } else {
                this.setState({ 
                    loading: false, 
                    usageData: data.body || data,
                    error: null 
                });
            }
        } catch (err) {
            this.setState({ 
                loading: false, 
                error: err.message || "An error occurred while fetching token usage" 
            });
        }
    }

    formatNumber(num) {
        if (num === undefined || num === null) return '0';
        const numValue = typeof num === 'string' ? parseFloat(num) : num;
        if (isNaN(numValue)) return '0';
        return numValue.toLocaleString();
    }

    formatCost(cost) {
        if (cost === undefined || cost === null) return '$0.000000';
        const costValue = typeof cost === 'string' ? parseFloat(cost) : cost;
        if (isNaN(costValue)) return '$0.000000';
        return `$${costValue.toFixed(6)}`;
    }

    formatDuration(seconds) {
        if (!seconds) return '0s';
        const secValue = typeof seconds === 'string' ? parseFloat(seconds) : seconds;
        if (isNaN(secValue) || secValue === 0) return '0s';
        if (secValue < 60) return `${secValue.toFixed(2)}s`;
        const minutes = Math.floor(secValue / 60);
        const remainingSeconds = secValue % 60;
        return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
    }

    getModelDisplayName(modelId) {
        const modelNames = {
            'amazon.nova-lite-v1:0': 'Nova Lite',
            'amazon.nova-pro-v1:0': 'Nova Pro',
            'amazon.nova-2-multimodal-embeddings-v1:0': 'Nova MME',
            'amazon_transcribe': 'Amazon Transcribe',
        };
        return modelNames[modelId] || modelId;
    }

    getTypeDisplayName(type) {
        const typeNames = {
            'image_understanding': 'Image Understanding',
            'video_understanding': 'Video Understanding',
            'nova_mme_video': 'Video Embedding',
            'nova_mme_image': 'Image Embedding',
            'tlabs_mme_video': 'TwelveLabs Video Embedding',
            'transcribe': 'Transcription',
        };
        return typeNames[type] || type;
    }

    // Get pricing information for a specific model and type
    getPricingInfo(modelId, type, region) {
        const pricingRegion = region || 'us-east-1';
        const regionPricing = REGIONAL_PRICING[pricingRegion];
        
        if (!regionPricing || !regionPricing[modelId] || !regionPricing[modelId][type]) {
            return null;
        }
        
        return regionPricing[modelId][type];
    }

    // Calculate cost for a single record based on regional pricing
    calculateRecordCost(record, region) {
        const pricingRegion = region || 'us-east-1';
        
        // Check if we have pricing for this region, model, and type
        const regionPricing = REGIONAL_PRICING[pricingRegion];
        if (!regionPricing) {
            return 0;
        }
        
        const modelPricing = regionPricing[record.model_id];
        if (!modelPricing) {
            return 0;
        }
        
        const typePricing = modelPricing[record.type];
        if (!typePricing) {
            return 0;
        }
        
        // Calculate based on pricing unit
        if (typePricing.unit === 'token') {
            const inputTokens = parseInt(record.input_tokens) || 0;
            const outputTokens = parseInt(record.output_tokens) || 0;
            const inputCost = (inputTokens / 1000) * typePricing.price_per_1k_input_tokens;
            const outputCost = (outputTokens / 1000) * typePricing.price_per_1k_output_tokens;
            return inputCost + outputCost;
        } else if (typePricing.unit === 'image') {
            const images = parseInt(record.number_of_image) || 0;
            return images * typePricing.price_per_image;
        } else if (typePricing.unit === 'second') {
            const duration = parseFloat(record.duration_s) || 0;
            return duration * typePricing.price_per_second;
        }
        
        return 0;
    }

    // Infer pricing unit from record if not explicitly provided
    inferPricingUnit(record) {
        if (record.pricing_unit) {
            return record.pricing_unit;
        }
        
        // Infer from available fields
        if (record.total_tokens || record.input_tokens || record.output_tokens) {
            return 'token';
        }
        if (record.number_of_image) {
            return 'image';
        }
        if (record.duration_s) {
            return 'second';
        }
        
        return 'unknown';
    }

    // Group usage records by type, model_id, and pricing_unit
    groupUsageRecords() {
        const { usageData } = this.state;
        if (!usageData || !usageData.usage_records) return {};

        const groups = {};
        const region = usageData.region || 'us-east-1';
        
        usageData.usage_records.forEach(record => {
            const pricingUnit = this.inferPricingUnit(record);
            const key = `${record.type}|${record.model_id}|${pricingUnit}`;
            
            if (!groups[key]) {
                groups[key] = {
                    type: record.type,
                    model_id: record.model_id,
                    pricing_unit: pricingUnit,
                    count: 0,
                    input_tokens: 0,
                    output_tokens: 0,
                    total_tokens: 0,
                    duration_s: 0,
                    cost_usd: 0,
                    number_of_images: 0,
                    names: new Set()
                };
            }

            groups[key].count += 1;
            groups[key].input_tokens += parseInt(record.input_tokens) || 0;
            groups[key].output_tokens += parseInt(record.output_tokens) || 0;
            groups[key].total_tokens += parseInt(record.total_tokens) || 0;
            groups[key].duration_s += parseFloat(record.duration_s) || 0;
            groups[key].number_of_images += parseInt(record.number_of_image) || 0;
            
            // Calculate cost using pricing configuration
            const calculatedCost = this.calculateRecordCost(record, region);
            groups[key].cost_usd += calculatedCost;
            
            if (record.name) {
                groups[key].names.add(record.name);
            }
        });

        // Convert names Set to Array
        Object.values(groups).forEach(group => {
            group.names = Array.from(group.names);
        });

        return groups;
    }

    // Calculate total cost from all records using pricing configuration
    calculateTotalCost() {
        const { usageData } = this.state;
        if (!usageData || !usageData.usage_records) return 0;

        const region = usageData.region || 'us-east-1';
        
        return usageData.usage_records.reduce((total, record) => {
            const cost = this.calculateRecordCost(record, region);
            return total + cost;
        }, 0);
    }

    renderSummaryCards() {
        const groups = this.groupUsageRecords();
        const groupsArray = Object.values(groups);
        
        // Separate by pricing unit
        const tokenGroups = groupsArray.filter(g => g.pricing_unit === 'token');
        const imageGroups = groupsArray.filter(g => g.pricing_unit === 'image');
        const durationGroups = groupsArray.filter(g => g.pricing_unit === 'second');
        const unknownGroups = groupsArray.filter(g => g.pricing_unit === 'unknown');
        
        const totalCost = this.calculateTotalCost();

        return (
            <SpaceBetween size="l">
                {/* Overall Total Cost */}
                <Container header={<Header variant="h3">Total Cost</Header>}>
                    <div className="usage-card">
                        <div className="usage-value cost-value" style={{ fontSize: '2rem' }}>
                            {this.formatCost(totalCost)}
                        </div>
                    </div>
                </Container>

                {/* Token-Based Groups */}
                {tokenGroups.length > 0 && (
                    <ExpandableSection 
                        headerText={`Token-Based Usage (${tokenGroups.length} ${tokenGroups.length === 1 ? 'group' : 'groups'})`}
                        defaultExpanded={false}
                    >
                        <SpaceBetween size="m">
                            {this.renderTokenBasedGroups(tokenGroups)}
                        </SpaceBetween>
                    </ExpandableSection>
                )}

                {/* Image-Based Groups */}
                {imageGroups.length > 0 && (
                    <ExpandableSection 
                        headerText={`Image-Based Usage (${imageGroups.length} ${imageGroups.length === 1 ? 'group' : 'groups'})`}
                        defaultExpanded={false}
                    >
                        <SpaceBetween size="m">
                            {this.renderImageBasedGroups(imageGroups)}
                        </SpaceBetween>
                    </ExpandableSection>
                )}

                {/* Duration-Based Groups */}
                {durationGroups.length > 0 && (
                    <ExpandableSection 
                        headerText={`Duration-Based Usage (${durationGroups.length} ${durationGroups.length === 1 ? 'group' : 'groups'})`}
                        defaultExpanded={false}
                    >
                        <SpaceBetween size="m">
                            {this.renderDurationBasedGroups(durationGroups)}
                        </SpaceBetween>
                    </ExpandableSection>
                )}

                {/* Unknown/Free Groups */}
                {unknownGroups.length > 0 && (
                    <ExpandableSection 
                        headerText={`Other Services (${unknownGroups.length} ${unknownGroups.length === 1 ? 'service' : 'services'})`}
                        defaultExpanded={false}
                    >
                        <SpaceBetween size="m">
                            {this.renderUnknownBasedGroups(unknownGroups)}
                        </SpaceBetween>
                    </ExpandableSection>
                )}
            </SpaceBetween>
        );
    }

    renderTokenBasedGroups(tokenGroups) {
        const { usageData } = this.state;
        const region = usageData?.region || 'us-east-1';
        
        return tokenGroups.map((item, index) => {
            const hasCost = item.cost_usd > 0;
            const pricingInfo = this.getPricingInfo(item.model_id, item.type, region);
            
            return (
                <Container key={index} variant="stacked">
                    <SpaceBetween size="s">
                        <div className="group-name-header">
                            <div>
                                <Badge color="green">{this.getTypeDisplayName(item.type)}</Badge>
                                <div style={{ fontSize: '0.85rem', color: '#5f6b7a', marginTop: '0.25rem' }}>
                                    Model: {item.model_id}
                                </div>
                                {item.names.length > 0 && (
                                    <div style={{ fontSize: '0.8rem', color: '#879596', marginTop: '0.25rem' }}>
                                        Names: {item.names.join(', ')}
                                    </div>
                                )}
                                {pricingInfo && (
                                    <div style={{ fontSize: '0.75rem', color: '#879596', marginTop: '0.25rem', fontStyle: 'italic' }}>
                                        Pricing: ${pricingInfo.price_per_1k_input_tokens.toFixed(6)}/1K input tokens, 
                                        ${pricingInfo.price_per_1k_output_tokens.toFixed(6)}/1K output tokens
                                    </div>
                                )}
                            </div>
                            <span className="group-cost" style={!hasCost ? { color: '#5f6b7a' } : {}}>
                                {hasCost ? this.formatCost(item.cost_usd) : 'N/A'}
                            </span>
                        </div>
                        <ColumnLayout columns={4} variant="text-grid">
                            <div>
                                <Box variant="awsui-key-label">Requests</Box>
                                <Box>{this.formatNumber(item.count)}</Box>
                            </div>
                            <div>
                                <Box variant="awsui-key-label">Input Tokens</Box>
                                <Box>{this.formatNumber(item.input_tokens)}</Box>
                            </div>
                            <div>
                                <Box variant="awsui-key-label">Output Tokens</Box>
                                <Box>{this.formatNumber(item.output_tokens)}</Box>
                            </div>
                            <div>
                                <Box variant="awsui-key-label">Total Tokens</Box>
                                <Box>{this.formatNumber(item.total_tokens)}</Box>
                            </div>
                        </ColumnLayout>
                    </SpaceBetween>
                </Container>
            );
        });
    }

    renderImageBasedGroups(imageGroups) {
        const { usageData } = this.state;
        const region = usageData?.region || 'us-east-1';
        
        return imageGroups.map((item, index) => {
            const hasCost = item.cost_usd > 0;
            const pricingInfo = this.getPricingInfo(item.model_id, item.type, region);
            
            return (
                <Container key={index} variant="stacked">
                    <SpaceBetween size="s">
                        <div className="group-name-header">
                            <div>
                                <Badge color="blue">{this.getTypeDisplayName(item.type)}</Badge>
                                <div style={{ fontSize: '0.85rem', color: '#5f6b7a', marginTop: '0.25rem' }}>
                                    Model: {item.model_id}
                                </div>
                                {item.names.length > 0 && (
                                    <div style={{ fontSize: '0.8rem', color: '#879596', marginTop: '0.25rem' }}>
                                        Names: {item.names.join(', ')}
                                    </div>
                                )}
                                {pricingInfo && (
                                    <div style={{ fontSize: '0.75rem', color: '#879596', marginTop: '0.25rem', fontStyle: 'italic' }}>
                                        Pricing: ${pricingInfo.price_per_image.toFixed(6)}/image
                                    </div>
                                )}
                            </div>
                            <span className="group-cost" style={!hasCost ? { color: '#5f6b7a' } : {}}>
                                {hasCost ? this.formatCost(item.cost_usd) : 'N/A'}
                            </span>
                        </div>
                        <ColumnLayout columns={hasCost ? 3 : 2} variant="text-grid">
                            <div>
                                <Box variant="awsui-key-label">Requests</Box>
                                <Box>{this.formatNumber(item.count)}</Box>
                            </div>
                            <div>
                                <Box variant="awsui-key-label">Total Images</Box>
                                <Box>{this.formatNumber(item.number_of_images || item.count)}</Box>
                            </div>
                            {hasCost && (
                                <div>
                                    <Box variant="awsui-key-label">Avg Cost/Image</Box>
                                    <Box>{this.formatCost(item.cost_usd / item.count)}</Box>
                                </div>
                            )}
                        </ColumnLayout>
                    </SpaceBetween>
                </Container>
            );
        });
    }

    renderDurationBasedGroups(durationGroups) {
        const { usageData } = this.state;
        const region = usageData?.region || 'us-east-1';
        
        return durationGroups.map((item, index) => {
            const hasCost = item.cost_usd > 0;
            const pricingInfo = this.getPricingInfo(item.model_id, item.type, region);
            const displayName = item.names.length > 0 ? item.names[0] : this.getTypeDisplayName(item.type);
            
            return (
                <Container key={index} variant="stacked">
                    <SpaceBetween size="s">
                        <div className="group-name-header">
                            <div>
                                <Badge color="purple">{displayName}</Badge>
                                <div style={{ fontSize: '0.85rem', color: '#5f6b7a', marginTop: '0.25rem' }}>
                                    Model: {item.model_id}
                                </div>
                                {item.names.length > 0 && (
                                    <div style={{ fontSize: '0.8rem', color: '#879596', marginTop: '0.25rem' }}>
                                        Names: {item.names.join(', ')}
                                    </div>
                                )}
                                {pricingInfo && (
                                    <div style={{ fontSize: '0.75rem', color: '#879596', marginTop: '0.25rem', fontStyle: 'italic' }}>
                                        Pricing: ${pricingInfo.price_per_second.toFixed(6)}/second
                                    </div>
                                )}
                            </div>
                            <span className="group-cost" style={!hasCost ? { color: '#5f6b7a' } : {}}>
                                {hasCost ? this.formatCost(item.cost_usd) : 'N/A'}
                            </span>
                        </div>
                        <ColumnLayout columns={2} variant="text-grid">
                            <div>
                                <Box variant="awsui-key-label">Requests</Box>
                                <Box>{this.formatNumber(item.count)}</Box>
                            </div>
                            <div>
                                <Box variant="awsui-key-label">Total Duration</Box>
                                <Box>{this.formatDuration(item.duration_s)}</Box>
                            </div>
                        </ColumnLayout>
                    </SpaceBetween>
                </Container>
            );
        });
    }

    renderUnknownBasedGroups(unknownGroups) {
        const { usageData } = this.state;
        const region = usageData?.region || 'us-east-1';
        
        return unknownGroups.map((item, index) => {
            const pricingInfo = this.getPricingInfo(item.model_id, item.type, region);
            
            return (
                <Container key={index} variant="stacked">
                    <SpaceBetween size="s">
                        <div className="group-name-header">
                            <div>
                                <Badge color="grey">{this.getTypeDisplayName(item.type)}</Badge>
                                <div style={{ fontSize: '0.85rem', color: '#5f6b7a', marginTop: '0.25rem' }}>
                                    Model: {item.model_id}
                                </div>
                                {item.names.length > 0 && (
                                    <div style={{ fontSize: '0.8rem', color: '#879596', marginTop: '0.25rem' }}>
                                        Names: {item.names.join(', ')}
                                    </div>
                                )}
                                {pricingInfo && pricingInfo.price_per_second && (
                                    <div style={{ fontSize: '0.75rem', color: '#879596', marginTop: '0.25rem', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                        <span>Pricing: ${pricingInfo.price_per_second.toFixed(6)}/second</span>
                                        {item.model_id === 'amazon_transcribe' && (
                                            <Popover
                                                dismissButton={false}
                                                position="top"
                                                size="medium"
                                                triggerType="custom"
                                                content={
                                                    <div style={{ fontSize: '0.85rem', maxWidth: '300px' }}>
                                                        <strong>Tiered Pricing Note:</strong>
                                                        <p style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
                                                            This cost estimate is based on single video transcription pricing. 
                                                            Amazon Transcribe uses tiered pricing - costs may be lower at scale.
                                                        </p>
                                                        <p style={{ marginBottom: 0 }}>
                                                            For detailed pricing tiers, see the{' '}
                                                            <a 
                                                                href="https://aws.amazon.com/transcribe/pricing/" 
                                                                target="_blank" 
                                                                rel="noopener noreferrer"
                                                            >
                                                                AWS Transcribe pricing page
                                                            </a>.
                                                        </p>
                                                    </div>
                                                }
                                            >
                                                <Button variant="inline-icon" iconName="status-info" ariaLabel="Transcribe pricing information" />
                                            </Popover>
                                        )}
                                    </div>
                                )}
                            </div>
                            <span className="group-cost" style={{ color: '#5f6b7a' }}>
                                {pricingInfo ? this.formatCost(item.cost_usd) : 'Free'}
                            </span>
                        </div>
                        <ColumnLayout columns={2} variant="text-grid">
                            <div>
                                <Box variant="awsui-key-label">Requests</Box>
                                <Box>{this.formatNumber(item.count)}</Box>
                            </div>
                            <div>
                                <Box variant="awsui-key-label">Total Duration</Box>
                                <Box>{this.formatDuration(item.duration_s)}</Box>
                            </div>
                        </ColumnLayout>
                    </SpaceBetween>
                </Container>
            );
        });
    }

    render() {
        const { loading, error, usageData } = this.state;

        if (loading) {
            return (
                <Container header={<Header variant="h2">Token Usage & Cost</Header>}>
                    <div style={{ textAlign: 'center', padding: '2rem' }}>
                        <Spinner size="large" />
                        <Box variant="p" padding={{ top: 's' }}>Loading usage data...</Box>
                    </div>
                </Container>
            );
        }

        if (error) {
            return (
                <Container header={<Header variant="h2">Token Usage & Cost</Header>}>
                    <Alert type="warning" header="Unable to load usage data">
                        {error}
                    </Alert>
                </Container>
            );
        }

        if (!usageData || !usageData.usage_records || usageData.usage_records.length === 0) {
            return (
                <Container header={<Header variant="h2">Token Usage & Cost</Header>}>
                    <Alert type="info" header="No usage data available">
                        No token usage or cost data found for this task.
                    </Alert>
                </Container>
            );
        }

        return (
            <div className="token-usage-container">
                <SpaceBetween size="m">
                    <ExpandableSection 
                        headerText="Cost Estimate Disclaimer"
                        variant="container"
                        defaultExpanded={false}
                    >
                        <SpaceBetween size="s">
                            <Alert type="info" header="Reference Only">
                                <SpaceBetween size="xs">
                                    <div>
                                        This cost estimate is provided as a reference to help you understand the cost allocation 
                                        for Amazon Bedrock-related services (image/video understanding foundation models and embeddings) 
                                        and Amazon Transcribe used in this video analysis task.
                                    </div>
                                    <div>
                                        <strong>Important Notes:</strong>
                                    </div>
                                    <ul style={{ marginTop: '0.5rem', marginBottom: '0.5rem', paddingLeft: '1.5rem' }}>
                                        <li>
                                            <strong>Not a Complete Cost:</strong> This estimate does not include other AWS service costs 
                                            such as S3 storage, Lambda compute, Step Functions orchestration, or data transfer fees.
                                        </li>
                                        <li>
                                            <strong>Transcribe Tiered Pricing:</strong> Amazon Transcribe uses tiered pricing based on 
                                            monthly usage volume. The costs shown here are calculated at the video level using standard 
                                            per-second rates. Production workloads at scale will typically see lower effective rates 
                                            due to volume discounts.
                                        </li>
                                        <li>
                                            <strong>For Precise Estimates:</strong> Please refer to the official AWS pricing pages for 
                                            detailed pricing tiers, volume discounts, and complete service costs.
                                        </li>
                                    </ul>
                                    <div>
                                        <strong>Pricing Resources:</strong>
                                    </div>
                                    <ul style={{ marginTop: '0.5rem', paddingLeft: '1.5rem' }}>
                                        <li>
                                            <a 
                                                href="https://aws.amazon.com/bedrock/pricing/" 
                                                target="_blank" 
                                                rel="noopener noreferrer"
                                            >
                                                AWS Bedrock Pricing
                                            </a>
                                        </li>
                                        <li>
                                            <a 
                                                href="https://aws.amazon.com/transcribe/pricing/" 
                                                target="_blank" 
                                                rel="noopener noreferrer"
                                            >
                                                AWS Transcribe Pricing (includes tiered pricing details)
                                            </a>
                                        </li>
                                    </ul>
                                </SpaceBetween>
                            </Alert>
                        </SpaceBetween>
                    </ExpandableSection>
                    
                    <Container 
                        header={
                            <Header 
                                variant="h2"
                                description={`Region: ${usageData.region || 'N/A'} (USD)`}
                            >
                                Token Usage & Cost
                            </Header>
                        }
                    >
                        {this.renderSummaryCards()}
                    </Container>
                </SpaceBetween>
            </div>
        );
    }
}

export default TokenUsage;
